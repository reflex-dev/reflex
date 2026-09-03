"""Tests for the reflex_otel instrumentor."""

import os
import subprocess
import sys
from collections.abc import Generator

import pytest
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util.http import ExcludeList
from reflex_base import otel
from reflex_base.environment import environment
from reflex_otel import ReflexInstrumentor


@pytest.fixture
def instrumentor() -> Generator[ReflexInstrumentor, None, None]:
    inst = ReflexInstrumentor()
    yield inst
    if inst._is_instrumented_by_opentelemetry:
        inst.uninstrument()


def test_instrument_toggles_trace_points(instrumentor: ReflexInstrumentor):
    assert otel.enabled is False
    instrumentor.instrument(tracer_provider=TracerProvider())
    assert otel.enabled is True
    instrumentor.uninstrument()
    assert otel.enabled is False


def test_instrument_is_idempotent(
    instrumentor: ReflexInstrumentor, caplog: pytest.LogCaptureFixture
):
    """A re-imported app module calls instrument() again; that must stay silent."""
    with caplog.at_level("WARNING"):
        instrumentor.instrument()
        instrumentor.instrument()
    assert otel.enabled is True
    assert "already instrumented" not in caplog.text


def test_instrument_configures_sdk_from_environment():
    """With OTEL_*_EXPORTER set and no SDK installed, instrument() sets the SDK up."""
    code = (
        "from opentelemetry import trace; from reflex_base import otel; "
        "from reflex_otel import ReflexInstrumentor; "
        "ReflexInstrumentor().instrument(); ReflexInstrumentor().instrument(); "
        "print(type(trace.get_tracer_provider()).__name__, otel.enabled)"
    )
    env = {
        **os.environ,
        "OTEL_TRACES_EXPORTER": "console",
        "OTEL_METRICS_EXPORTER": "none",
        "OTEL_LOGS_EXPORTER": "none",
    }
    out = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert out.stdout.split() == ["TracerProvider", "True"]
    assert "already instrumented" not in out.stderr
    # Without the exporter variables the SDK is left alone (proxy provider).
    env.pop("OTEL_TRACES_EXPORTER")
    env["OTEL_METRICS_EXPORTER"] = ""
    out = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert out.stdout.split() == ["ProxyTracerProvider", "True"]


def test_sdk_disabled_keeps_trace_points_off(
    instrumentor: ReflexInstrumentor, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    instrumentor.instrument()
    assert instrumentor.is_instrumented_by_opentelemetry
    assert otel.enabled is False
    assert otel.asgi_middleware is None
    instrumentor.uninstrument()
    assert otel.enabled is False


_SEMCONV_PROBE = """
import asyncio, os
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from reflex_base import otel
from reflex_otel import ReflexInstrumentor

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
ReflexInstrumentor().instrument(tracer_provider=provider)

async def app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b""})

async def receive():
    return {"type": "http.request", "body": b"", "more_body": False}

async def send(message):
    pass

scope = {"type": "http", "method": "GET", "path": "/x", "raw_path": b"/x", "query_string": b"",
         "headers": [], "scheme": "http", "server": ("localhost", 80), "http_version": "1.1"}
asyncio.run(otel.asgi_middleware(app)(scope, receive, send))
(span,) = exporter.get_finished_spans()
print(os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"], sorted(span.attributes))
"""


@pytest.mark.parametrize(
    ("preset", "expect_new", "expect_old"),
    [(None, True, False), ("http/dup", True, True)],
)
def test_opts_into_stable_http_semconv(
    preset: str | None, expect_new: bool, expect_old: bool
):
    """The middleware emits the stable HTTP names unless the operator chose otherwise.

    The contrib packages read the variable once per process, so this runs in a
    fresh interpreter.
    """
    env = {k: v for k, v in os.environ.items() if k != "OTEL_SEMCONV_STABILITY_OPT_IN"}
    if preset is not None:
        env["OTEL_SEMCONV_STABILITY_OPT_IN"] = preset
    out = subprocess.run(
        [sys.executable, "-c", _SEMCONV_PROBE],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    value, _, keys = out.partition(" ")
    assert value == (preset or "http")
    # Server spans carry url.scheme/url.path under the stable conventions.
    assert ("url.scheme" in keys) is expect_new
    assert ("http.scheme" in keys) is expect_old


def test_no_runtime_dependency_check(instrumentor: ReflexInstrumentor):
    """reflex-base is a hard dependency: the resolver enforces the floor, not instrument()."""
    assert instrumentor.instrumentation_dependencies() == ()


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


@pytest.mark.parametrize(
    ("variable", "value", "ping_disabled"),
    [
        ("OTEL_PYTHON_REFLEX_EXCLUDED_URLS", "", False),
        ("OTEL_PYTHON_EXCLUDED_URLS", "", False),
        ("OTEL_PYTHON_REFLEX_EXCLUDED_URLS", "/health", False),
        ("OTEL_PYTHON_EXCLUDED_URLS", "/ping,/health", True),
    ],
)
def test_excluded_urls_env_empty_means_none(
    instrumentor: ReflexInstrumentor,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
    value: str,
    ping_disabled: bool,
):
    """A variable set to an empty string disables the defaults, like an empty kwarg."""
    monkeypatch.delenv("OTEL_PYTHON_REFLEX_EXCLUDED_URLS", raising=False)
    monkeypatch.delenv("OTEL_PYTHON_EXCLUDED_URLS", raising=False)
    monkeypatch.setenv(variable, value)
    instrumentor.instrument(tracer_provider=TracerProvider())
    assert otel.asgi_middleware is not None

    async def app(scope, receive, send): ...

    wrapped = otel.asgi_middleware(app)
    assert isinstance(wrapped, OpenTelemetryMiddleware)
    assert isinstance(wrapped.excluded_urls, ExcludeList)
    assert wrapped.excluded_urls.url_disabled("/ping") is ping_disabled


@pytest.mark.parametrize("mounted", [False, True])
def test_default_exclusions_cover_mounted_frontend_assets(
    instrumentor: ReflexInstrumentor, monkeypatch: pytest.MonkeyPatch, mounted: bool
):
    """Static chunks served by the backend in prod mode get no spans by default."""
    monkeypatch.setenv(
        environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.name, str(mounted).lower()
    )
    instrumentor.instrument(tracer_provider=TracerProvider())
    assert otel.asgi_middleware is not None

    async def app(scope, receive, send): ...

    wrapped = otel.asgi_middleware(app)
    assert isinstance(wrapped, OpenTelemetryMiddleware)
    excluded = wrapped.excluded_urls
    assert isinstance(excluded, ExcludeList)
    assert excluded.url_disabled("http://h/ping")
    assert excluded.url_disabled("http://h/assets/index-abc.js") is mounted
    assert not excluded.url_disabled("http://h/api/assets/list")


async def test_asgi_span_redacts_client_token(instrumentor: ReflexInstrumentor):
    """The websocket connect URL carries the client token; spans must not."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    seen: list[str] = []
    instrumentor.instrument(
        tracer_provider=provider,
        server_request_hook=lambda span, scope: seen.append(scope["path"]),
    )
    assert otel.asgi_middleware is not None

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():  # noqa: RUF029
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        pass

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/_event/",
        "raw_path": b"/_event/",
        "query_string": b"token=secret-token&transport=websocket&EIO=4",
        "headers": [],
        "scheme": "http",
        "server": ("localhost", 80),
        "http_version": "1.1",
    }
    await otel.asgi_middleware(app)(scope, receive, send)
    (span,) = exporter.get_finished_spans()
    assert span.attributes is not None
    urls = [v for v in span.attributes.values() if isinstance(v, str) and "token=" in v]
    assert urls, span.attributes
    assert all("secret-token" not in v and "token=REDACTED" in v for v in urls)
    assert all("secret-token" not in str(v) for v in span.attributes.values())
    # The user's own hook still runs, after the redaction.
    assert seen == ["/_event/"]


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
