"""Bare Starlette + Socket.IO server mirroring Reflex's websocket substrate.

Serves the same stack Reflex runs on (uvicorn, Starlette mount at ``/_event``,
python-socketio ``AsyncServer`` on the ``/_event`` namespace) with a handler
that answers every event with a canned state-update payload. Round-trip
latency against this server isolates the substrate cost, so the difference
against a real Reflex app is the framework's own event-pipeline overhead.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import socketio
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount


class _EchoNamespace(socketio.AsyncNamespace):
    """Namespace answering every event with a fixed update payload."""

    def __init__(self, namespace: str, response: dict[str, Any]):
        """Initialize the namespace.

        Args:
            namespace: Socket.IO namespace, matching Reflex's event namespace.
            response: Payload emitted back for every received event.
        """
        super().__init__(namespace)
        self._response = response

    async def on_connect(self, sid: str, environ: dict) -> None:
        """Accept every connection.

        Args:
            sid: Socket.IO session id.
            environ: Connection request information.
        """

    async def on_event(self, sid: str, data: Any) -> None:
        """Answer an event with the canned update.

        Args:
            sid: Socket.IO session id.
            data: Received event payload, intentionally unused.
        """
        await self.emit("event", self._response, to=sid)


class BaselineSocketServer:
    """Context manager serving the bare substrate on an ephemeral port."""

    def __init__(self, response: dict[str, Any]):
        """Configure the server without starting it.

        Args:
            response: Payload emitted back for every received event.
        """
        sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",
            cors_credentials=True,
            allow_upgrades=False,
            transports=["websocket"],
        )
        sio.register_namespace(_EchoNamespace("/_event", response))
        socket_app = socketio.ASGIApp(sio, socketio_path="")
        self._server = uvicorn.Server(
            uvicorn.Config(
                app=Starlette(routes=[Mount("/_event", app=socket_app)]),
                host="127.0.0.1",
                port=0,
                log_level="warning",
            )
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self.url = ""

    def __enter__(self) -> BaselineSocketServer:
        """Start the server and resolve its ephemeral URL.

        Returns:
            The running server.

        Raises:
            TimeoutError: If the server does not bind within ten seconds.
        """
        self._thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (
                self._server.started
                and (servers := self._server.servers)
                and (sockets := servers[0].sockets)
            ):
                host, port = sockets[0].getsockname()[:2]
                self.url = f"http://{host}:{port}"
                return self
            time.sleep(0.01)
        self._server.should_exit = True
        msg = "Baseline socket server did not start within 10 seconds."
        raise TimeoutError(msg)

    def __exit__(self, *exc_info) -> None:
        """Stop the server and join its thread.

        Args:
            exc_info: Exception information, intentionally unused.
        """
        self._server.should_exit = True
        self._thread.join(timeout=10)
