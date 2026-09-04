"""TCP proxy adding a fixed one-way delay in each direction (emulates network RTT on loopback)."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections import deque


class DelayProxy:
    """Loopback TCP proxy that delays every chunk by a fixed one-way latency."""

    def __init__(self, upstream_port: int, one_way_ms: float):
        """Create the proxy.

        Args:
            upstream_port: Port of the real server on 127.0.0.1.
            one_way_ms: Delay added in each direction (RTT is twice this).
        """
        self.upstream_port = upstream_port
        self.delay = one_way_ms / 1000
        self.port: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    async def _pipe(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        loop = asyncio.get_running_loop()
        pending: deque[tuple[float, bytes | None]] = deque()
        wake = asyncio.Event()

        async def flusher():
            while True:
                while not pending:
                    wake.clear()
                    await wake.wait()
                due, data = pending[0]
                now = loop.time()
                if due > now:
                    await asyncio.sleep(due - now)
                pending.popleft()
                if data is None:
                    break
                writer.write(data)
                try:
                    await writer.drain()
                except Exception:
                    return
            with contextlib.suppress(Exception):
                writer.close()

        task = asyncio.create_task(flusher())
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                pending.append((loop.time() + self.delay, data))
                wake.set()
        except Exception:
            pass
        pending.append((loop.time() + self.delay, None))
        wake.set()
        await task

    async def _handle(self, reader, writer):
        try:
            up_reader, up_writer = await asyncio.open_connection(
                "127.0.0.1", self.upstream_port
            )
        except Exception:
            writer.close()
            return
        await asyncio.gather(
            self._pipe(reader, up_writer), self._pipe(up_reader, writer)
        )

    async def _serve(self):
        server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = server.sockets[0].getsockname()[1]
        self._ready.set()
        async with server:
            await server.serve_forever()

    def start(self) -> int:
        """Start the proxy on a background thread.

        Returns:
            The local port the proxy listens on.
        """

        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            with contextlib.suppress(Exception):
                self._loop.run_until_complete(self._serve())

        threading.Thread(target=run, daemon=True).start()
        self._ready.wait(5)
        assert self.port
        return self.port
