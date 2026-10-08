"""A server that answers the event generator like the playground does, without reflex.

It speaks either protocol of reflex's event websocket (see
:mod:`reflex_bench.drivers.events`) and, like reflex, refuses the websocket on
the other one's path, so the generator detects which: the plain protocol's
connect frame and handshake or Socket.IO's engine.io open and namespace ack,
pings, and one delta per event. The hydration events set ``is_hydrated``;
every other event gets a delta that echoes its ``payload["seq"]``. The
generator's calibration (``selftest.events.calibrate``) runs it in a separate
process, and the generator's tests subclass it to script delays and faults.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import multiprocessing
import os
import urllib.parse
import uuid
from collections.abc import AsyncIterator, Sequence
from http import HTTPStatus
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from reflex_bench.drivers.events import (
    BOOT_KEY,
    CODECS,
    CONNECT,
    DISCONNECTED,
    EVENT,
    HANDSHAKE,
    HYDRATE_AND_LOAD_EVENT,
    HYDRATE_EVENT,
    HYDRATED_VAR,
    KILL_GRACE_S,
    MAX_FRAME_BYTES,
    ON_LOAD_EVENT,
    PING,
    ROOT_STATE,
    SIO_CONNECT_FRAME,
    SIO_OPEN_PREFIX,
    SIO_PING,
    WireProtocol,
    event_loop,
)

# The plain protocol's version, announced in its handshake.
PROTOCOL_VERSION = 2


class EchoServer:
    """Answers the generator's frames as a reflex app does, one event at a time per connection."""

    def __init__(
        self,
        *,
        delta_key: str,
        seq_var: str,
        protocol: WireProtocol = "websocket",
        ping_interval_s: float = 25.0,
        ping_timeout_s: float = 120.0,
    ) -> None:
        """Configure the answers.

        Args:
            delta_key: The state whose delta echoes the sequence number.
            seq_var: The var that echoes it.
            protocol: The protocol to speak.
            ping_interval_s: Seconds between pings.
            ping_timeout_s: The ping timeout announced in the handshake.
        """
        self.delta_key = delta_key
        self.seq_var = seq_var
        self.codec = CODECS[protocol]
        self.ping_interval_s = ping_interval_s
        self.ping_timeout_s = ping_timeout_s
        self._path = urllib.parse.urlsplit(self.codec.url("http://echo", "")).path

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
            process_request=self._route,
        ) as server:
            yield next(iter(server.sockets)).getsockname()[1]

    def _route(self, connection: ServerConnection, request: Request) -> Response | None:
        """Refuse the websocket on any path but the protocol's, as reflex does.

        Args:
            connection: The connection.
            request: Its upgrade request.

        Returns:
            ``None`` to accept, or a 404.
        """
        if urllib.parse.urlsplit(request.path).path == self._path:
            return None
        return connection.respond(HTTPStatus.NOT_FOUND, "Not Found\n")

    async def handle(self, ws: ServerConnection) -> None:
        """Serve one connection until it closes or leaves the session.

        The codec decodes the client's frames too: Socket.IO's packets are the
        same both ways, so its namespace join decodes as ``HANDSHAKE``.

        Args:
            ws: The connection.
        """
        sid = uuid.uuid4().hex
        codec = self.codec
        if codec.greets:
            await ws.send(
                SIO_OPEN_PREFIX
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
                args = codec.parse(message)
                if args is None:
                    # Socket.IO's pong.
                    continue
                name = args[0]
                if name == EVENT:
                    await self.on_event(ws, args[1])
                elif name in {CONNECT, HANDSHAKE}:
                    await self.on_connect(ws, sid)
                    # The plain protocol's connect carries the boot event.
                    auth = args[1] if len(args) > 1 else None
                    if isinstance(auth, dict) and BOOT_KEY in auth:
                        await self.on_event(ws, auth[BOOT_KEY])
                elif name == DISCONNECTED:
                    return
        except ConnectionClosed:
            pass
        finally:
            pinger.cancel()

    async def _ping(self, ws: ServerConnection) -> None:
        """Send pings; the generator answers them.

        Args:
            ws: The connection.
        """
        ping = SIO_PING if self.codec.protocol == "socketio" else self.codec.emit(PING)
        with contextlib.suppress(ConnectionClosed):
            while True:
                await asyncio.sleep(self.ping_interval_s)
                await ws.send(ping)

    async def on_connect(self, ws: ServerConnection, sid: str) -> None:
        """Acknowledge the connect.

        Args:
            ws: The connection.
            sid: The session id.
        """
        if self.codec.protocol == "socketio":
            await ws.send(SIO_CONNECT_FRAME + json.dumps({"sid": sid}))
            return
        await ws.send(
            self.codec.emit(
                HANDSHAKE,
                {
                    "ping_interval": self.ping_interval_s,
                    "ping_timeout": self.ping_timeout_s,
                    "protocol": PROTOCOL_VERSION,
                    "max_message_size": MAX_FRAME_BYTES,
                },
            )
        )

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
            The hydration events get the root state's ``is_hydrated``: false
            for ``hydrate``, true for ``on_load_internal`` and
            ``hydrate_and_load``; any other event gets its sequence number
            echoed.
        """
        name = event["name"]
        if name in {HYDRATE_EVENT, ON_LOAD_EVENT, HYDRATE_AND_LOAD_EVENT}:
            delta = {ROOT_STATE: {HYDRATED_VAR: name != HYDRATE_EVENT}}
        else:
            delta = {self.delta_key: {self.seq_var: event["payload"]["seq"]}}
        return self.codec.emit(EVENT, {"delta": delta, "events": []})


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
