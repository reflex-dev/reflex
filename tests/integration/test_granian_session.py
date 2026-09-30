"""Browser session transport against a real Granian ASGI server."""

import asyncio
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import socketio
from granian.constants import Interfaces
from granian.server.embed import Server
from reflex_base.registry import RegistrationContext

import reflex as rx
from reflex.istate.manager.memory import StateManagerMemory
from reflex.state import BaseState


async def test_granian_session_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, unused_tcp_port: int
):
    """Socket state works before cookie exchange and survives a bound reconnect.

    Args:
        monkeypatch: Environment and test-only compilation overrides.
        tmp_path: Isolated backend working directory.
        unused_tcp_port: Ephemeral port selected by pytest.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_MODE", "enforce")
    monkeypatch.setenv("REFLEX_SESSION_SECRET", "s" * 32)
    origin = f"http://127.0.0.1:{unused_tcp_port}"
    (tmp_path / "rxconfig.py").write_text(
        f"import reflex as rx\nconfig = rx.Config(app_name='granian_session', api_url={origin!r})\n",
        encoding="utf-8",
    )
    exchange_started, release_exchange = asyncio.Event(), asyncio.Event()

    def hold_exchange(asgi):
        """Delay only the HTTP credential exchange while WebSockets run.

        Args:
            asgi: The backend application.

        Returns:
            The gated ASGI application.
        """

        async def gated(scope, receive, send):
            """Run requests after any session exchange barrier.

            Args:
                scope: The request scope.
                receive: The request message receiver.
                send: The response message sender.
            """
            if scope["type"] == "http" and scope["path"] == "/_reflex/session":
                exchange_started.set()
                await release_exchange.wait()
            await asgi(scope, receive, send)

        return gated

    with RegistrationContext.ensure_context().fork() as registry:

        class CounterState(BaseState):
            """State served without a frontend build."""

            count: int = 0

            @rx.event
            def increment(self):
                """Increment the persisted counter."""
                self.count += 1

        app = rx.App(_state=CounterState, api_transformer=hold_exchange)
        app._state_manager = StateManagerMemory()
        monkeypatch.setattr(app, "_compile", Mock())
        server = Server(
            app(), interface=Interfaces.ASGI, port=unused_tcp_port, log_enabled=False
        )
        server_task = asyncio.create_task(server.serve())
        namespace = registry.config.get_event_namespace()
        tokens, sessions, updates = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
        client = socketio.AsyncClient(reconnection=False)
        client.on("new_token", tokens.put_nowait, namespace=namespace)
        client.on("session_token", sessions.put_nowait, namespace=namespace)
        client.on("event", updates.put_nowait, namespace=namespace)
        exchange_task = None

        async def increment(expected):
            """Wait for a real state event to return the expected delta.

            Args:
                expected: The expected counter value.
            """
            await client.emit(
                "event",
                {"name": f"{CounterState.get_full_name()}.increment"},
                namespace=namespace,
            )
            while True:
                update = await asyncio.wait_for(updates.get(), 5)
                if (
                    update["delta"]
                    .get(CounterState.get_full_name(), {})
                    .get("count_rx_state_")
                    == expected
                ):
                    return

        try:
            async with httpx.AsyncClient(base_url=origin) as http:
                for _ in range(200):
                    if server_task.done():
                        await server_task
                    try:
                        if (await http.get("/ping")).status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    await asyncio.sleep(0.025)
                else:
                    pytest.fail("Granian did not become ready")
                await client.connect(
                    origin,
                    namespaces=[namespace],
                    socketio_path=namespace,
                    transports=["websocket"],
                )
                token = await asyncio.wait_for(tokens.get(), 5)
                credential = await asyncio.wait_for(sessions.get(), 5)
                exchange_task = asyncio.create_task(
                    http.post(
                        "/_reflex/session",
                        json={"session_token": credential},
                        headers={"Origin": origin, "Reflex-Client-Token": token},
                    )
                )
                await asyncio.wait_for(exchange_started.wait(), 5)
                await increment(1)
                assert not exchange_task.done()
                release_exchange.set()
                response = await exchange_task
                assert response.status_code == 200, response.text
                assert response.json()["client_token"] == token
                assert "HttpOnly" in response.headers["set-cookie"]
                cookie = response.headers["set-cookie"].partition(";")[0]
                await client.disconnect()
                assert app.event_namespace is not None
                for _ in range(200):
                    if token not in app.event_namespace.token_to_sid:
                        break
                    await asyncio.sleep(0.025)
                else:
                    pytest.fail("Disconnected socket retained its client token")
                await client.connect(
                    f"{origin}?token={token}",
                    headers={"Cookie": cookie},
                    namespaces=[namespace],
                    socketio_path=namespace,
                    transports=["websocket"],
                )
                await increment(2)
                assert tokens.empty()
                assert sessions.empty()
        finally:
            release_exchange.set()
            if exchange_task is not None:
                await asyncio.gather(exchange_task, return_exceptions=True)
            await client.disconnect()
            server.stop()
            await asyncio.wait_for(server_task, 10)
