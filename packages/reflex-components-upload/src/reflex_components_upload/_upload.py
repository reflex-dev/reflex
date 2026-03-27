"""Backend upload helpers and routes for Reflex apps."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, cast

from python_multipart.multipart import MultipartParser, parse_options_header
from reflex_core import constants
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException, _user_safe_decode
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from typing_extensions import Self

from reflex.utils import exceptions

if TYPE_CHECKING:
    from reflex_core.event import EventHandler
    from reflex_core.utils.types import Receive, Scope, Send

    from reflex.app import App
    from reflex.state import BaseState


@dataclasses.dataclass(frozen=True)
class UploadFile(StarletteUploadFile):
    """A file uploaded to the server.

    Args:
        file: The standard Python file object (non-async).
        filename: The original file name.
        size: The size of the file in bytes.
        headers: The headers of the request.
    """

    file: BinaryIO

    path: Path | None = dataclasses.field(default=None)

    size: int | None = dataclasses.field(default=None)

    headers: Headers = dataclasses.field(default_factory=Headers)

    @property
    def filename(self) -> str | None:
        """Get the name of the uploaded file.

        Returns:
            The name of the uploaded file.
        """
        return self.name

    @property
    def name(self) -> str | None:
        """Get the name of the uploaded file.

        Returns:
            The name of the uploaded file.
        """
        if self.path:
            return self.path.name
        return None


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class UploadChunk:
    """A chunk of uploaded file data."""

    filename: str
    offset: int
    content_type: str
    data: bytes


class UploadChunkIterator(AsyncIterator[UploadChunk]):
    """An async iterator over uploaded file chunks."""

    __slots__ = (
        "_chunks",
        "_closed",
        "_condition",
        "_consumer_task",
        "_error",
        "_maxsize",
    )

    def __init__(self, *, maxsize: int = 8):
        """Initialize the iterator.

        Args:
            maxsize: Maximum number of chunks to buffer before blocking producers.
        """
        self._maxsize = maxsize
        self._chunks: deque[UploadChunk] = deque()
        self._condition = asyncio.Condition()
        self._closed = False
        self._error: Exception | None = None
        self._consumer_task: asyncio.Task[Any] | None = None

    def __aiter__(self) -> Self:
        """Return the iterator itself.

        Returns:
            The upload chunk iterator.
        """
        return self

    async def __anext__(self) -> UploadChunk:
        """Yield the next available upload chunk.

        Returns:
            The next upload chunk.

        Raises:
            _error: Any error forwarded from the upload producer.
            StopAsyncIteration: When all chunks have been consumed.
        """
        async with self._condition:
            while not self._chunks and not self._closed:
                await self._condition.wait()

            if self._chunks:
                chunk = self._chunks.popleft()
                self._condition.notify_all()
                return chunk

            if self._error is not None:
                raise self._error
            raise StopAsyncIteration

    def set_consumer_task(self, task: asyncio.Task[Any]) -> None:
        """Track the task consuming this iterator.

        Args:
            task: The background task consuming upload chunks.
        """
        self._consumer_task = task
        task.add_done_callback(self._wake_waiters)

    async def push(self, chunk: UploadChunk) -> None:
        """Push a new chunk into the iterator.

        Args:
            chunk: The chunk to push.

        Raises:
            RuntimeError: If the iterator is already closed or the consumer exited early.
        """
        async with self._condition:
            while len(self._chunks) >= self._maxsize and not self._closed:
                self._raise_if_consumer_finished()
                await self._condition.wait()

            if self._closed:
                msg = "Upload chunk iterator is closed."
                raise RuntimeError(msg)

            self._raise_if_consumer_finished()
            self._chunks.append(chunk)
            self._condition.notify_all()

    async def finish(self) -> None:
        """Mark the iterator as complete."""
        async with self._condition:
            if self._closed:
                return
            self._closed = True
            self._condition.notify_all()

    async def fail(self, error: Exception) -> None:
        """Mark the iterator as failed.

        Args:
            error: The error to raise from the iterator.
        """
        async with self._condition:
            if self._closed:
                return
            self._closed = True
            self._error = error
            self._condition.notify_all()

    def _raise_if_consumer_finished(self) -> None:
        """Raise if the consumer task exited before draining the iterator.

        Raises:
            RuntimeError: If the consumer task completed before draining the iterator.
        """
        if self._consumer_task is None or not self._consumer_task.done():
            return

        try:
            task_exc = self._consumer_task.exception()
        except asyncio.CancelledError as err:
            task_exc = err

        msg = "Upload handler returned before consuming all upload chunks."
        if task_exc is not None:
            raise RuntimeError(msg) from task_exc
        raise RuntimeError(msg)

    def _wake_waiters(self, task: asyncio.Task[Any]) -> None:
        """Wake any producers or consumers blocked on the iterator condition.

        Args:
            task: The completed consumer task.
        """
        task.get_loop().create_task(self._notify_waiters())

    async def _notify_waiters(self) -> None:
        """Notify tasks waiting on the iterator condition."""
        async with self._condition:
            self._condition.notify_all()


@dataclasses.dataclass(kw_only=True, slots=True)
class _UploadChunkPart:
    """Track the current multipart file part for upload streaming."""

    content_disposition: bytes | None = None
    field_name: str = ""
    filename: str | None = None
    content_type: str = ""
    item_headers: list[tuple[bytes, bytes]] = dataclasses.field(default_factory=list)
    offset: int = 0
    bytes_emitted: int = 0
    is_upload_chunk: bool = False


@dataclasses.dataclass(kw_only=True, slots=True)
class _UploadChunkMultipartParser:
    """Streaming multipart parser for streamed upload files."""

    headers: Headers
    stream: AsyncGenerator[bytes, None]
    chunk_iter: UploadChunkIterator
    _charset: str = ""
    _current_partial_header_name: bytes = b""
    _current_partial_header_value: bytes = b""
    _current_part: _UploadChunkPart = dataclasses.field(
        default_factory=_UploadChunkPart
    )
    _chunks_to_emit: deque[UploadChunk] = dataclasses.field(default_factory=deque)
    _seen_upload_chunk: bool = False
    _part_count: int = 0
    _emitted_chunk_count: int = 0
    _emitted_bytes: int = 0
    _stream_chunk_count: int = 0

    def on_part_begin(self) -> None:
        """Reset parser state for a new multipart part."""
        self._current_part = _UploadChunkPart()

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        """Record streamed chunk data for the current part."""
        if (
            not self._current_part.is_upload_chunk
            or self._current_part.filename is None
        ):
            return

        message_bytes = data[start:end]
        self._chunks_to_emit.append(
            UploadChunk(
                filename=self._current_part.filename,
                offset=self._current_part.offset + self._current_part.bytes_emitted,
                content_type=self._current_part.content_type,
                data=message_bytes,
            )
        )
        self._current_part.bytes_emitted += len(message_bytes)
        self._emitted_chunk_count += 1
        self._emitted_bytes += len(message_bytes)

    def on_part_end(self) -> None:
        """Emit a zero-byte chunk for empty file parts."""
        if (
            self._current_part.is_upload_chunk
            and self._current_part.filename is not None
            and self._current_part.bytes_emitted == 0
        ):
            self._chunks_to_emit.append(
                UploadChunk(
                    filename=self._current_part.filename,
                    offset=self._current_part.offset,
                    content_type=self._current_part.content_type,
                    data=b"",
                )
            )
            self._emitted_chunk_count += 1

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        """Accumulate multipart header field bytes."""
        self._current_partial_header_name += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        """Accumulate multipart header value bytes."""
        self._current_partial_header_value += data[start:end]

    def on_header_end(self) -> None:
        """Store the completed multipart header."""
        field = self._current_partial_header_name.lower()
        if field == b"content-disposition":
            self._current_part.content_disposition = self._current_partial_header_value
        self._current_part.item_headers.append((
            field,
            self._current_partial_header_value,
        ))
        self._current_partial_header_name = b""
        self._current_partial_header_value = b""

    def on_headers_finished(self) -> None:
        """Parse upload metadata from multipart headers."""
        disposition, options = parse_options_header(
            self._current_part.content_disposition
        )
        if disposition != b"form-data":
            msg = "Invalid upload chunk disposition."
            raise MultiPartException(msg)

        try:
            field_name = _user_safe_decode(options[b"name"], self._charset)
        except KeyError as err:
            msg = 'The Content-Disposition header field "name" must be provided.'
            raise MultiPartException(msg) from err

        try:
            filename = _user_safe_decode(options[b"filename"], self._charset)
        except KeyError:
            # Ignore non-file form fields entirely.
            return
        filename = Path(filename.lstrip("/")).name

        content_type = ""
        for header_name, header_value in self._current_part.item_headers:
            if header_name == b"content-type":
                content_type = _user_safe_decode(header_value, self._charset)
                break

        self._current_part.field_name = field_name
        self._current_part.filename = filename
        self._current_part.content_type = content_type
        self._current_part.offset = 0
        self._current_part.bytes_emitted = 0
        self._current_part.is_upload_chunk = True
        self._seen_upload_chunk = True
        self._part_count += 1

    def on_end(self) -> None:
        """Finalize parser callbacks."""

    async def _flush_emitted_chunks(self) -> None:
        """Push parsed upload chunks into the handler iterator."""
        while self._chunks_to_emit:
            await self.chunk_iter.push(self._chunks_to_emit.popleft())

    async def parse(self) -> None:
        """Parse the incoming request stream and push chunks to the iterator.

        Raises:
            MultiPartException: If the request is not valid multipart upload data.
            RuntimeError: If the upload handler exits before consuming all chunks.
        """
        _, params = parse_options_header(self.headers["Content-Type"])
        charset = params.get(b"charset", "utf-8")
        if isinstance(charset, bytes):
            charset = charset.decode("latin-1")
        self._charset = charset

        try:
            boundary = params[b"boundary"]
        except KeyError as err:
            msg = "Missing boundary in multipart."
            raise MultiPartException(msg) from err

        callbacks = {
            "on_part_begin": self.on_part_begin,
            "on_part_data": self.on_part_data,
            "on_part_end": self.on_part_end,
            "on_header_field": self.on_header_field,
            "on_header_value": self.on_header_value,
            "on_header_end": self.on_header_end,
            "on_headers_finished": self.on_headers_finished,
            "on_end": self.on_end,
        }
        parser = MultipartParser(boundary, cast(Any, callbacks))

        async for chunk in self.stream:
            self._stream_chunk_count += 1
            parser.write(chunk)
            await self._flush_emitted_chunks()

        parser.finalize()
        await self._flush_emitted_chunks()


class _UploadStreamingResponse(StreamingResponse):
    """Streaming response that always releases upload form resources."""

    _on_finish: Callable[[], Awaitable[None]]

    def __init__(
        self,
        *args: Any,
        on_finish: Callable[[], Awaitable[None]],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._on_finish = on_finish

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self._on_finish()


def _require_upload_headers(request: Request) -> tuple[str, str]:
    """Extract the required upload headers from a request.

    Args:
        request: The incoming request.

    Returns:
        The client token and event handler name.

    Raises:
        HTTPException: If the upload headers are missing.
    """
    token = request.headers.get("reflex-client-token")
    handler = request.headers.get("reflex-event-handler")

    if not token or not handler:
        raise HTTPException(
            status_code=400,
            detail="Missing reflex-client-token or reflex-event-handler header.",
        )

    return token, handler


async def _get_upload_runtime_handler(
    app: App,
    token: str,
    handler_name: str,
) -> tuple[BaseState, EventHandler]:
    """Resolve the runtime state and event handler for an upload request.

    Args:
        app: The Reflex app.
        token: The client token.
        handler_name: The fully qualified event handler name.

    Returns:
        The root state instance and resolved event handler.
    """
    from reflex.state import _substate_key

    substate_token = _substate_key(token, handler_name.rpartition(".")[0])
    state = await app.state_manager.get_state(substate_token)
    _current_state, event_handler = state._get_event_handler(handler_name)
    return state, event_handler


def _seed_upload_router_data(state: BaseState, token: str) -> None:
    """Ensure upload-launched handlers have the client token in router state.

    Background upload handlers use ``StateProxy`` which derives its mutable-state
    token from ``self.router.session.client_token``. Upload requests do not flow
    through the normal websocket event pipeline, so we seed the token here.

    Args:
        state: The root state instance.
        token: The client token from the upload request.
    """
    from reflex.state import RouterData

    router_data = dict(state.router_data)
    if router_data.get(constants.RouteVar.CLIENT_TOKEN) == token:
        return

    router_data[constants.RouteVar.CLIENT_TOKEN] = token
    state.router_data = router_data
    state.router = RouterData.from_router_data(router_data)


async def _upload_buffered_file(
    request: Request,
    app: App,
    *,
    token: str,
    handler_name: str,
    handler_upload_param: tuple[str, Any],
) -> Response:
    """Handle buffered uploads on the standard upload endpoint.

    Returns:
        A streaming response for the buffered upload.
    """
    from reflex_core.event import Event
    from reflex_core.utils.exceptions import UploadValueError

    try:
        form_data = await request.form()
    except ClientDisconnect:
        return Response()

    form_data_closed = False

    async def _close_form_data() -> None:
        """Close the parsed form data exactly once."""
        nonlocal form_data_closed
        if form_data_closed:
            return
        form_data_closed = True
        await form_data.close()

    def _create_upload_event() -> Event:
        """Create an upload event using the live Starlette temp files.

        Returns:
            The upload event backed by the parsed files.
        """
        files = form_data.getlist("files")
        file_uploads = []
        for file in files:
            if not isinstance(file, StarletteUploadFile):
                raise UploadValueError(
                    "Uploaded file is not an UploadFile." + str(file)
                )
            file_uploads.append(
                UploadFile(
                    file=file.file,
                    path=Path(file.filename.lstrip("/")) if file.filename else None,
                    size=file.size,
                    headers=file.headers,
                )
            )

        return Event(
            token=token,
            name=handler_name,
            payload={handler_upload_param[0]: file_uploads},
        )

    event: Event | None = None
    try:
        event = _create_upload_event()
    finally:
        if event is None:
            await _close_form_data()

    if event is None:
        msg = "Upload event was not created."
        raise RuntimeError(msg)

    async def _ndjson_updates():
        """Process the upload event, generating ndjson updates.

        Yields:
            Each state update as newline-delimited JSON.
        """
        async with app.state_manager.modify_state_with_links(
            event.substate_token, event=event
        ) as state:
            async for update in state._process(event):
                update = await app._postprocess(state, event, update)
                yield update.json() + "\n"

    return _UploadStreamingResponse(
        _ndjson_updates(),
        media_type="application/x-ndjson",
        on_finish=_close_form_data,
    )


def _background_upload_accepted_response() -> StreamingResponse:
    """Return a minimal ndjson response for background upload dispatch."""
    from reflex.state import StateUpdate

    def _accepted_updates():
        yield StateUpdate(final=True).json() + "\n"

    return StreamingResponse(
        _accepted_updates(),
        media_type="application/x-ndjson",
        status_code=202,
    )


async def _upload_chunk_file(
    request: Request,
    app: App,
    *,
    token: str,
    handler_name: str,
    handler_upload_param: tuple[str, Any],
    acknowledge_on_upload_endpoint: bool,
) -> Response:
    """Handle a streaming upload request.

    Returns:
        The streaming upload response.
    """
    from reflex_core.event import Event

    chunk_iter = UploadChunkIterator(maxsize=8)
    event = Event(
        token=token,
        name=handler_name,
        payload={handler_upload_param[0]: chunk_iter},
    )

    async with app.state_manager.modify_state_with_links(
        event.substate_token,
        event=event,
    ) as state:
        _seed_upload_router_data(state, token)
        task = app._process_background(state, event)

    if task is None:
        msg = f"@rx.event(background=True) is required for upload_files_chunk handler `{handler_name}`."
        return JSONResponse({"detail": msg}, status_code=400)

    chunk_iter.set_consumer_task(task)

    parser = _UploadChunkMultipartParser(
        headers=request.headers,
        stream=request.stream(),
        chunk_iter=chunk_iter,
    )

    try:
        await parser.parse()
    except ClientDisconnect:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return Response()
    except (MultiPartException, RuntimeError, ValueError) as err:
        await chunk_iter.fail(err)
        return JSONResponse({"detail": str(err)}, status_code=400)

    try:
        await chunk_iter.finish()
    except RuntimeError as err:
        return JSONResponse({"detail": str(err)}, status_code=400)

    if acknowledge_on_upload_endpoint:
        return _background_upload_accepted_response()
    return Response(status_code=202)


def upload(app: App):
    """Upload files, dispatching to buffered or streaming handling.

    Args:
        app: The app to upload the file for.

    Returns:
        The upload function.
    """

    async def upload_file(request: Request):
        """Upload a file.

        Args:
            request: The Starlette request object.

        Returns:
            The upload response.

        Raises:
            UploadValueError: If the handler does not have a supported annotation.
            UploadTypeError: If a non-streaming upload is wired to a background task.
            HTTPException: when the request does not include token / handler headers.
        """
        from reflex_core.event import (
            resolve_upload_chunk_handler_param,
            resolve_upload_handler_param,
        )

        token, handler_name = _require_upload_headers(request)
        _state, event_handler = await _get_upload_runtime_handler(
            app, token, handler_name
        )

        if event_handler.is_background:
            try:
                handler_upload_param = resolve_upload_chunk_handler_param(event_handler)
            except exceptions.UploadValueError:
                pass
            else:
                return await _upload_chunk_file(
                    request,
                    app,
                    token=token,
                    handler_name=handler_name,
                    handler_upload_param=handler_upload_param,
                    acknowledge_on_upload_endpoint=True,
                )

        handler_upload_param = resolve_upload_handler_param(event_handler)
        return await _upload_buffered_file(
            request,
            app,
            token=token,
            handler_name=handler_name,
            handler_upload_param=handler_upload_param,
        )

    return upload_file
