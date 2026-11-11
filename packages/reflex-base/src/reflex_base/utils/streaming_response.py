"""Internal helpers for streaming responses."""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable, Generator
from functools import partial
from typing import Any

import anyio
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse

from reflex_base.utils.types import Message, Receive, Scope, Send


def _parse_asgi_spec_version(scope: Scope) -> tuple[int, ...]:
    """Parse the ASGI spec version from a scope.

    Args:
        scope: The ASGI scope.

    Returns:
        The parsed ASGI spec version, or ``(2, 0)`` if parsing fails.
    """
    raw_spec = scope.get("asgi", {}).get("spec_version", "2.0")
    try:
        return tuple(int(part) for part in str(raw_spec).split("."))
    except (TypeError, ValueError):
        return (2, 0)


@contextlib.contextmanager
def _collapse_excgroups() -> Generator[None, None, None]:
    """Collapse single-item exception groups to their underlying exception."""
    collapsed_exc: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        collapsed_exc = exc
        while isinstance(collapsed_exc, BaseExceptionGroup):
            nested_exceptions = collapsed_exc.exceptions
            if len(nested_exceptions) != 1:
                break
            collapsed_exc = nested_exceptions[0]
        if collapsed_exc is exc:
            raise
    if collapsed_exc is not None:
        raise collapsed_exc


class DisconnectAwareStreamingResponse(StreamingResponse):
    """Streaming response with a guaranteed finish callback."""

    _on_finish: Callable[[], Awaitable[None]]
    _on_disconnect: Callable[[], None] | None

    def __init__(
        self,
        *args: Any,
        on_finish: Callable[[], Awaitable[None]],
        on_disconnect: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the response.

        Args:
            args: Positional args forwarded to ``StreamingResponse``.
            on_finish: Cleanup callback to run exactly once when the response ends.
            on_disconnect: Sync callback invoked when the client disconnects.
            kwargs: Keyword args forwarded to ``StreamingResponse``.
        """
        super().__init__(*args, **kwargs)
        self._on_finish = on_finish
        self._on_disconnect = on_disconnect

    def _notify_disconnect(self) -> None:
        """Invoke the on_disconnect callback if one was provided."""
        if self._on_disconnect is not None:
            self._on_disconnect()

    async def _close_body_iterator(self) -> None:
        """Close the body iterator if it supports ``aclose``."""
        aclose = getattr(self.body_iterator, "aclose", None)
        if aclose is not None:
            await aclose()

    async def stream_response(self, send: Send) -> None:
        """Stream the body, holding the response start until the first body message.

        A body iterator that raises before yielding then leaves the response
        unstarted, so the app can still answer with an error status.

        Args:
            send: The ASGI send callable.
        """
        start: Message | None = None

        async def send_start_with_body(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
                return
            if start is not None:
                await send(start)
                start = None
            await send(message)

        await super().stream_response(send_start_with_body)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve the response and always run the finish callback."""
        spec_version = _parse_asgi_spec_version(scope)

        try:
            if spec_version < (2, 4):
                with _collapse_excgroups():
                    async with anyio.create_task_group() as task_group:

                        async def wrap(func: Callable[[], Awaitable[None]]) -> None:
                            await func()
                            task_group.cancel_scope.cancel()

                        task_group.start_soon(wrap, partial(self.stream_response, send))

                        if self._on_disconnect is not None:

                            async def _disconnect_then_notify() -> None:
                                await self.listen_for_disconnect(receive)
                                self._notify_disconnect()

                            await wrap(_disconnect_then_notify)
                        else:
                            await wrap(partial(self.listen_for_disconnect, receive))
            else:
                try:
                    await self.stream_response(send)
                except OSError as err:
                    self._notify_disconnect()
                    raise ClientDisconnect from err
        finally:
            await self._close_body_iterator()
            await self._on_finish()

        if self.background is not None:
            await self.background()


__all__ = ["DisconnectAwareStreamingResponse"]
