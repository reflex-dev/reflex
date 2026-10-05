"""Exercise real buffered/chunk uploads and streamed custom API events."""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import reflex as rx
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from reflex_base import otel
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.utils.streaming_response import DisconnectAwareStreamingResponse
from reflex_base.utils.types import ASGIApp, Receive, Scope, Send
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

records: list[dict] = []
exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))


def instrument_asgi(app: ASGIApp) -> OpenTelemetryMiddleware:
    """Wrap the real backend in request tracing.

    Args:
        app: The backend ASGI callable.

    Returns:
        The instrumented ASGI app.
    """
    return OpenTelemetryMiddleware(app, tracer_provider=provider)


def observe_response(asgi_app: ASGIApp) -> ASGIApp:
    """Record real HTTP response completion independently of browser callbacks.

    Args:
        asgi_app: The backend ASGI app.

    Returns:
        A wrapper preserving the actual upload and API responses.
    """

    async def wrapped(scope: Scope, receive: Receive, send: Send) -> None:
        """Observe an HTTP response's final body.

        Args:
            scope: The ASGI request scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        headers = dict(scope.get("headers", []))
        token = headers.get(b"reflex-client-token", b"").decode()

        async def observed_send(message: dict[str, Any]):
            """Forward a message and timestamp the final body.

            Args:
                message: The ASGI response message.
            """
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                records.append({
                    "label": "response.end",
                    "detail": scope.get("path"),
                    "token": token,
                    "time": time.monotonic(),
                })

        try:
            await asgi_app(scope, receive, observed_send)
        finally:
            if scope.get("type") == "http":
                records.append({
                    "label": "response.exit",
                    "detail": scope.get("path"),
                    "token": token,
                    "time": time.monotonic(),
                })

    return wrapped


otel.enable(tracer_provider=provider, asgi_middleware_factory=instrument_asgi)


def record(label: str, detail: str = "") -> None:
    """Save event lineage and timing from the real running backend.

    Args:
        label: A phase identifier.
        detail: Additional information about this phase.
    """
    context = EventContext.get()
    records.append({
        "label": label,
        "detail": detail,
        "token": context.token,
        "txid": context.txid,
        "parent_txid": context.parent_txid,
        "time": time.monotonic(),
    })


class UploadState(rx.State):
    """Keep browser-visible upload state and ordinary event counters."""

    upload_status: str = "idle"
    uploaded_bytes: int = 0
    upload_count: int = 0
    ordinary_count: int = 0
    delayed_count: int = 0
    recovered: int = 0
    chunk_bytes: int = 0
    chunk_done: bool = False
    api_count: int = 0
    http_status: str = "idle"
    nav_status: str = "idle"

    @rx.event
    async def buffered(self, files: list[rx.UploadFile]):
        """Read a real multipart upload, then chain a delayed completion event.

        Args:
            files: The buffered uploaded files.

        Yields:
            A flush followed by the delayed completion event.

        Raises:
            RuntimeError: For the deliberately failing upload fixture.
        """
        name = files[0].name or "unnamed"
        record("upload.start", name)
        self.uploaded_bytes = 0
        for file in files:
            self.uploaded_bytes += len(await file.read())
        self.upload_status = "received:" + name
        yield
        if name == "fail.txt":
            await asyncio.sleep(0.05)
            record("upload.expected_failure", name)
            message = "expected upload recovery probe"
            raise RuntimeError(message)
        yield UploadState.finish_upload(name)
        record("upload.handler_return", name)

    @rx.event(background=True)
    async def finish_upload(self, name: str):
        """Keep the HTTP response open until a chained background task completes.

        Args:
            name: The uploaded file's test fixture name.
        """
        record("upload.tail_start", name)
        try:
            await asyncio.sleep(2.4 if name.startswith("slow") else 0.65)
            async with self:
                self.upload_count += 1
                self.upload_status = "done:" + name
            record("upload.tail_end", name)
        except asyncio.CancelledError:
            record("upload.tail_cancel", name)
            raise

    @rx.event
    def ordinary(self):
        """Apply an unrelated ordinary websocket event."""
        self.ordinary_count += 1
        record("ordinary.end")

    @rx.event
    async def delayed(self):
        """Run a delayed unrelated event in another browser session."""
        record("delayed.start")
        try:
            await asyncio.sleep(1.3)
            self.delayed_count += 1
            record("delayed.end")
        except asyncio.CancelledError:
            record("delayed.cancel")
            raise

    @rx.event(background=True)
    async def recover(self):
        """Send a recovery delta after the failed upload response has ended."""
        record("recovery.start")
        await asyncio.sleep(0.35)
        async with self:
            self.recovered += 1
            self.upload_status = "recovered"
        record("recovery.end")

    @rx.event(background=True)
    async def chunks(self, chunk_iter: rx.UploadChunkIterator):
        """Consume real streamed file chunks under the upload request's span.

        Args:
            chunk_iter: The streamed multipart file chunks.
        """
        record("chunk.start")
        total = 0
        async for chunk in chunk_iter:
            total += len(chunk.data)
        async with self:
            self.chunk_bytes = total
            self.chunk_done = True
        record("chunk.end", str(total))

    @rx.event
    async def http_slow(self):
        """Stream a state delta, then remain in flight until completion or disconnect.

        Yields:
            A first delta followed by a delayed final delta.
        """
        record("http.start")
        self.http_status = "started"
        yield
        try:
            await asyncio.sleep(2.4)
            self.http_status = "done"
            record("http.end")
            yield
        except asyncio.CancelledError:
            record("http.cancel")
            raise

    @rx.event
    def api_parent(self):
        """Chain a child event from a real HTTP request.

        Returns:
            The child event.
        """
        record("api.parent")
        return UploadState.api_child

    @rx.event
    def api_child(self):
        """Apply the HTTP request's chained state update."""
        self.api_count += 1
        record("api.child")

    @rx.event(background=True)
    async def nav_slow(self):
        """Keep the old page's on-load chain in flight while an upload is active."""
        record("nav.start")
        async with self:
            self.nav_status = "slow-started"
        try:
            await asyncio.sleep(3.0)
            async with self:
                self.nav_status = "slow-finished"
            record("nav.end")
        except asyncio.CancelledError:
            record("nav.cancel")
            raise

    @rx.event
    def nav_new(self):
        """Complete the new page's on-load without waiting for the old chain."""
        self.nav_status = "new-loaded"
        record("nav.new")


def backend_exception(exception: Exception):
    """Chain delayed recovery after the intentional failing upload.

    Args:
        exception: The backend handler exception.

    Returns:
        A recovery event for the expected upload failure.

    Raises:
        Exception: Any unexpected backend error.
    """
    if str(exception) != "expected upload recovery probe":
        raise exception
    record("exception.handler", type(exception).__name__)
    return UploadState.recover


async def evidence(request: Request) -> JSONResponse:  # noqa: RUF029
    """Return real event phases and completed trace spans.

    Args:
        request: The HTTP request.

    Returns:
        Backend evidence captured by the running process.
    """
    spans = [
        {
            "name": span.name,
            "kind": span.kind.name,
            "span_id": f"{span.context.span_id:016x}",
            "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else None,
            "attributes": dict(span.attributes),
        }
        for span in exporter.get_finished_spans()
    ]
    return JSONResponse({"records": records, "spans": spans})


async def enqueue(request: Request) -> JSONResponse:
    """Enqueue a top-level event beneath an actual HTTP request span.

    Args:
        request: The HTTP request identifying a browser token.

    Returns:
        An acknowledgement after the event and its child complete.
    """
    token = request.query_params["token"]
    future = await app.event_processor.enqueue(
        token, Event(name=UploadState.get_full_name() + ".api_parent")
    )
    await future.wait_all()
    return JSONResponse({"complete": True})


async def stream(request: Request) -> DisconnectAwareStreamingResponse:  # noqa: RUF029
    """Return a real streamed event response whose consumer can disconnect.

    Args:
        request: The HTTP request identifying the browser token.

    Returns:
        A streamed state-delta response.
    """
    token = request.query_params["token"]
    event = Event(name=UploadState.get_full_name() + ".http_slow")

    async def updates() -> AsyncGenerator[str, None]:
        """Yield the event's real state deltas as NDJSON.

        Yields:
            Encoded state deltas from the published event processor.
        """
        async for delta in app.event_processor.enqueue_stream_delta(token, event):
            yield json.dumps(delta) + "\n"

    async def finish() -> None:  # noqa: RUF029
        """Record completion of the custom HTTP streaming consumer."""
        records.append({
            "label": "http.response_finish",
            "detail": "",
            "token": token,
            "time": time.monotonic(),
        })

    return DisconnectAwareStreamingResponse(
        updates(), media_type="application/x-ndjson", on_finish=finish
    )


def controls() -> rx.Component:
    """Build real upload, ordinary-event and navigation controls.

    Returns:
        The shared controls rendered on all test routes.
    """
    return rx.vstack(
        rx.heading("Published alpha: upload stream isolation"),
        rx.text(UploadState.router.session.client_token, id="token"),
        rx.upload.root(rx.text("Select buffered file"), id="buffered"),
        rx.button(
            "Upload buffered",
            id="upload",
            on_click=UploadState.buffered(rx.upload_files(upload_id="buffered")),
        ),
        rx.upload.root(rx.text("Select chunked file"), id="chunked"),
        rx.button(
            "Upload chunks",
            id="upload-chunks",
            on_click=UploadState.chunks(rx.upload_files_chunk(upload_id="chunked")),
        ),
        rx.button("Ordinary", id="ordinary", on_click=UploadState.ordinary),
        rx.button("Delayed ordinary", id="delayed", on_click=UploadState.delayed),
        rx.text(UploadState.upload_status, id="upload-status"),
        rx.text(UploadState.uploaded_bytes, id="uploaded-bytes"),
        rx.text(UploadState.upload_count, id="upload-count"),
        rx.text(UploadState.ordinary_count, id="ordinary-count"),
        rx.text(UploadState.delayed_count, id="delayed-count"),
        rx.text(UploadState.recovered, id="recovered"),
        rx.text(UploadState.chunk_bytes, id="chunk-bytes"),
        rx.text(rx.cond(UploadState.chunk_done, "done", "waiting"), id="chunk-done"),
        rx.text(UploadState.api_count, id="api-count"),
        rx.text(UploadState.nav_status, id="nav-status"),
        rx.link("Slow page", href="/slow", id="slow-link"),
        rx.link("New page", href="/new", id="new-link"),
        rx.link("Index", href="/", id="index-link"),
        padding="24px",
    )


api = Starlette(
    routes=[
        Route("/api/evidence", evidence),
        Route("/api/enqueue", enqueue, methods=["POST"]),
        Route("/api/stream", stream, methods=["POST"]),
    ]
)
app = rx.App(
    api_transformer=[api, observe_response], backend_exception_handler=backend_exception
)
app.add_page(controls, route="/")
app.add_page(controls, route="/slow", on_load=UploadState.nav_slow)
app.add_page(controls, route="/new", on_load=UploadState.nav_new)
