"""Tests for the reflex_otel instrumentor."""

import subprocess
import sys
from collections.abc import Generator
from importlib.metadata import entry_points

import pytest
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util.http import ExcludeList
from reflex_base import otel
from reflex_otel import ReflexInstrumentor


@pytest.fixture
def instrumentor() -> Generator[ReflexInstrumentor, None, None]:
    inst = ReflexInstrumentor()
    yield inst
    if inst._is_instrumented_by_opentelemetry:
        inst.uninstrument()


def test_plugin_import_does_not_load_the_instrumentor():
    """rxconfig.py imports OtelPlugin in every CLI process; keep that cheap."""
    code = (
        "import sys; from reflex_otel import OtelPlugin; "
        "print('opentelemetry.instrumentation.instrumentor' in sys.modules); "
        "from reflex_otel import ReflexInstrumentor; print(ReflexInstrumentor.__name__)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    ).stdout.split()
    assert out == ["False", "ReflexInstrumentor"]


def test_entry_point_resolves_the_instrumentor():
    (ep,) = [
        e
        for e in entry_points(group="opentelemetry_instrumentor")
        if e.name == "reflex"
    ]
    assert ep.load() is ReflexInstrumentor


def test_instrument_toggles_trace_points(instrumentor: ReflexInstrumentor):
    assert otel.enabled is False
    instrumentor.instrument(tracer_provider=TracerProvider())
    assert otel.enabled is True
    instrumentor.uninstrument()
    assert otel.enabled is False


def test_instrument_is_idempotent(instrumentor: ReflexInstrumentor):
    instrumentor.instrument()
    instrumentor.instrument()
    assert otel.enabled is True


def test_dependencies_target_reflex_base(instrumentor: ReflexInstrumentor):
    (dep,) = instrumentor.instrumentation_dependencies()
    assert dep.startswith("reflex-base")


def test_instrument_installs_asgi_middleware(instrumentor: ReflexInstrumentor):
    instrumentor.instrument(tracer_provider=TracerProvider())
    assert otel.asgi_middleware is not None

    async def app(scope, receive, send): ...

    wrapped = otel.asgi_middleware(app)
    assert isinstance(wrapped, OpenTelemetryMiddleware)
    assert wrapped.app is app
    instrumentor.uninstrument()
    assert otel.asgi_middleware is None


@pytest.mark.parametrize(
    ("excluded_urls", "ping_disabled"),
    [(None, True), ("", False), ("/health", False)],
)
def test_excluded_urls_only_defaults_when_omitted(
    instrumentor: ReflexInstrumentor,
    excluded_urls: str | None,
    ping_disabled: bool,
):
    kwargs = {} if excluded_urls is None else {"excluded_urls": excluded_urls}
    instrumentor.instrument(tracer_provider=TracerProvider(), **kwargs)
    assert otel.asgi_middleware is not None

    async def app(scope, receive, send): ...

    wrapped = otel.asgi_middleware(app)
    assert isinstance(wrapped, OpenTelemetryMiddleware)
    # Older ASGI instrumentation stores strings verbatim and then calls
    # .url_disabled() on them; always hand it a parsed ExcludeList.
    assert isinstance(wrapped.excluded_urls, ExcludeList)
    assert wrapped.excluded_urls.url_disabled("/ping") is ping_disabled


async def test_asgi_middleware_handles_requests(instrumentor: ReflexInstrumentor):
    """The wrapped app must serve requests, including at the ASGI floor.

    Older ASGI instrumentation stores excluded_urls verbatim, so a raw string
    made every request raise AttributeError.
    """
    instrumentor.instrument(tracer_provider=TracerProvider())
    assert otel.asgi_middleware is not None
    served: list[str] = []

    async def app(scope, receive, send):
        served.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():  # noqa: RUF029
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        pass

    wrapped = otel.asgi_middleware(app)
    for path in ("/ping", "/_event"):
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("localhost", 80),
            "http_version": "1.1",
        }
        await wrapped(scope, receive, send)
    assert served == ["/ping", "/_event"]
