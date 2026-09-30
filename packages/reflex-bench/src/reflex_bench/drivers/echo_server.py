"""A socket.io server that answers the event generator like the playground does, without reflex.

It speaks the frames of reflex's event websocket (see
:mod:`reflex_bench.drivers.events`): the engine.io handshake, the namespace ack,
pings, and one delta per event. The hydration events set ``is_hydrated``; every
other event gets a delta that echoes its ``payload["seq"]``. The generator's
calibration (``selftest.events.calibrate``) runs against it in a separate
process, and the generator's tests subclass it to script delays and faults.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import multiprocessing
import os
import uuid
from collections.abc import AsyncIterator, Sequence
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from reflex_bench.drivers.events import (
    CONNECT_FRAME,
    DISCONNECT_FRAME,
    EVENT_PREFIX,
    HYDRATE_EVENT,
    HYDRATED_VAR,
    KILL_GRACE_S,
    NAMESPACE,
    ON_LOAD_EVENT,
    PING,
    ROOT_STATE,
    emit_frame,
    event_loop,
)


class EchoServer:
    """Answers the generator's frames as a reflex app does, one event at a time per connection."""

    def __init__(
        self,
        *,
        delta_key: str,
        seq_var: str,
        ping_interval_s: float = 25.0,
        ping_timeout_s: float = 120.0,
    ) -> None:
        """Configure the answers.

        Args:
            delta_key: The state whose delta echoes the sequence number.
            seq_var: The var that echoes it.
            ping_interval_s: Seconds between engine.io pings.
            ping_timeout_s: The ping timeout announced in the handshake.
        """
        self.delta_key = delta_key
        self.seq_var = seq_var
        self.ping_interval_s = ping_interval_s
        self.ping_timeout_s = ping_timeout_s

    @contextlib.asynccontextmanager
    async def serve(self, host: str, port: int) -> AsyncIterator[int]:
        """Listen for connections while the context is open.

        Args:
            host: The address to bind.
            port: The port; 0 picks a free one.

        Yields:
            The bound port.
        """
        # Like granian, no permessage-deflate: frames go out uncompressed.
        async with serve(
            self.handle,
            host,
            port,
            compression=None,
            max_size=None,
            ping_interval=None,
        ) as server:
            yield next(iter(server.sockets)).getsockname()[1]

    async def handle(self, ws: ServerConnection) -> None:
        """Serve one connection until it closes or leaves the namespace.

        Args:
            ws: The connection.
        """
        sid = uuid.uuid4().hex
        await ws.send(
            "0"
            + json.dumps({
                "sid": sid,
                "upgrades": [],
                "pingInterval": int(self.ping_interval_s * 1000),
                "pingTimeout": int(self.ping_timeout_s * 1000),
                "maxPayload": 1_000_000,
            })
        )
        pinger = asyncio.create_task(self._ping(ws))
        try:
            async for message in ws:
                if isinstance(message, str) and message.startswith(EVENT_PREFIX):
                    name, *args = json.loads(message[len(EVENT_PREFIX) :])
                    if name == "event":
                        await self.on_event(ws, args[0])
                elif message == CONNECT_FRAME:
                    await self.on_connect(ws, sid)
                elif message == DISCONNECT_FRAME:
                    return
        except ConnectionClosed:
            pass
        finally:
            pinger.cancel()

    async def _ping(self, ws: ServerConnection) -> None:
        """Send engine.io pings; the generator answers them.

        Args:
            ws: The connection.
        """
        with contextlib.suppress(ConnectionClosed):
            while True:
                await asyncio.sleep(self.ping_interval_s)
                await ws.send(PING)

    async def on_connect(self, ws: ServerConnection, sid: str) -> None:
        """Acknowledge the namespace connect.

        Args:
            ws: The connection.
            sid: The session id.
        """
        await ws.send(f"40{NAMESPACE}," + json.dumps({"sid": sid}))

    async def on_event(self, ws: ServerConnection, event: dict[str, Any]) -> None:
        """Answer one event.

        Args:
            ws: The connection.
            event: The event, as the frontend sends it.
        """
        await ws.send(self.reply(event))

    def reply(self, event: dict[str, Any]) -> str:
        """Build the delta that answers an event.

        Args:
            event: The event.

        Returns:
            ``hydrate`` and ``on_load_internal`` get the root state's
            ``is_hydrated`` (false, then true); any other event gets its
            sequence number echoed.
        """
        name = event["name"]
        if name in {HYDRATE_EVENT, ON_LOAD_EVENT}:
            delta = {ROOT_STATE: {HYDRATED_VAR: name == ON_LOAD_EVENT}}
        else:
            delta = {self.delta_key: {self.seq_var: event["payload"]["seq"]}}
        return emit_frame("event", {"delta": delta, "events": []})


def _serve_process(
    conn: Connection, delta_key: str, seq_var: str, cpus: Sequence[int] | None
) -> None:
    """Run an echo server in this process until the parent closes the pipe or terminates it.

    Args:
        conn: Receives the bound port; closing its other end stops the server.
        delta_key: The state whose delta echoes the sequence number.
        seq_var: The var that echoes it.
        cpus: The CPUs to run on (Linux), or ``None``.
    """
    if cpus is not None and hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, cpus)

    async def main() -> None:
        server = EchoServer(delta_key=delta_key, seq_var=seq_var)
        async with server.serve("127.0.0.1", 0) as port:
            conn.send(port)
            # The parent holds the pipe open while it needs the server, and
            # its end closes however the parent exits.
            parent_gone = asyncio.Event()
            asyncio.get_running_loop().add_reader(conn.fileno(), parent_gone.set)
            await parent_gone.wait()

    event_loop().run_until_complete(main())


class EchoProcess:
    """An :class:`EchoServer` in a spawned process, so it runs on its own CPUs."""

    def __init__(
        self, *, delta_key: str, seq_var: str, cpus: Sequence[int] | None = None
    ) -> None:
        """Plan the server; nothing starts yet.

        Args:
            delta_key: The state whose delta echoes the sequence number.
            seq_var: The var that echoes it.
            cpus: The CPUs to run on (Linux), or ``None``.
        """
        self._args = (delta_key, seq_var, None if cpus is None else list(cpus))
        self._proc: BaseProcess | None = None
        self._conn: Connection | None = None

    def start(self, timeout: float = 30.0) -> str:
        """Start the server.

        Args:
            timeout: Seconds to wait until it listens.

        Returns:
            Its base URL, like the backend URL of a started app.

        Raises:
            RuntimeError: When it does not listen in time.
        """
        context = multiprocessing.get_context("spawn")
        conn, child = context.Pipe()
        proc = self._proc = context.Process(
            target=_serve_process,
            args=(child, *self._args),
            name="reflex-bench-echo",
            daemon=True,
        )
        proc.start()
        child.close()
        self._conn = conn
        try:
            port = conn.recv() if conn.poll(timeout) else None
        except (EOFError, OSError):
            port = None
        if port is None:
            self.stop()
            msg = f"the echo server did not listen within {timeout:g} s (exit code {proc.exitcode})"
            raise RuntimeError(msg)
        return f"http://127.0.0.1:{port}"

    @property
    def pid(self) -> int:
        """The server process's pid, e.g. to read its memory.

        Returns:
            The pid.

        Raises:
            RuntimeError: Before :meth:`start`.
        """
        if self._proc is None or self._proc.pid is None:
            msg = "the echo server was not started"
            raise RuntimeError(msg)
        return self._proc.pid

    def stop(self) -> None:
        """Stop the server; safe to call again."""
        proc, conn = self._proc, self._conn
        if conn is not None:
            conn.close()
        if proc is None:
            return
        proc.terminate()
        proc.join(KILL_GRACE_S)
        if proc.is_alive():
            proc.kill()
            proc.join(KILL_GRACE_S)
