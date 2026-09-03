"""OpenTelemetry instrumentation for the Reflex framework."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Collection
from typing import TYPE_CHECKING, Any, Literal

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from reflex_base import otel
from reflex_base.config import get_config
from reflex_base.environment import environment

if TYPE_CHECKING:
    from opentelemetry.trace import Span

_instruments = ("reflex-base >= 0.9.7.post45.dev0",)

# Per-message websocket spans are noise; Reflex emits one span per event instead.
_ASGI_EXCLUDED_SPANS: list[Literal["receive", "send"]] = ["receive", "send"]
# Frontend health polling; override with excluded_urls or the variables below.
_DEFAULT_EXCLUDED_URLS = "/ping"
_EXCLUDED_URLS_ENV_VARS = (
    "OTEL_PYTHON_REFLEX_EXCLUDED_URLS",
    "OTEL_PYTHON_EXCLUDED_URLS",
)
# The websocket connects with ?token=<client token>; the token authorizes access
# to the session's state, so it is stripped from the URL attributes the ASGI
# middleware records (old and current HTTP semantic conventions).
_URL_ATTRIBUTES = ("http.url", "url.full", "url.query")
_TOKEN_PARAM = re.compile(r"\btoken=[^&#]*")
_REDACTED_TOKEN = "token=REDACTED"


def _default_excluded_urls() -> str:
    """URL patterns the ASGI middleware skips unless configured otherwise.

    Returns:
        The frontend health poll, plus the compiled frontend's static assets
        when the backend serves them (``reflex run --env prod`` on one port),
        where every chunk of a page load would otherwise get a span.
    """
    patterns = [_DEFAULT_EXCLUDED_URLS]
    if environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.get():
        assets = re.escape(get_config().prepend_frontend_path("/assets/"))
        patterns.append(f"^[a-z]+://[^/]+{assets}")
    return ",".join(patterns)


def _redact_token(span: Span, scope: Any) -> None:
    """Strip the client token from a server span's URL attributes.

    Args:
        span: The span the ASGI middleware opened for the request.
        scope: The ASGI scope (unused).
    """
    attributes = getattr(span, "attributes", None)
    if not attributes:
        return
    for key in _URL_ATTRIBUTES:
        value = attributes.get(key)
        if isinstance(value, str) and "token=" in value:
            span.set_attribute(key, _TOKEN_PARAM.sub(_REDACTED_TOKEN, value))


def _server_request_hook(
    user_hook: Callable[[Span, Any], None] | None,
) -> Callable[[Span, Any], None]:
    """Chain the token redaction in front of the user's server request hook.

    Args:
        user_hook: The hook passed to ``instrument()``, if any.

    Returns:
        The hook to install on the ASGI middleware.
    """
    if user_hook is None:
        return _redact_token

    def hook(span: Span, scope: Any) -> None:
        _redact_token(span, scope)
        user_hook(span, scope)

    return hook


class ReflexInstrumentor(BaseInstrumentor):
    """Enable the trace points and metrics built into the Reflex runtime.

    Usage::

        ReflexInstrumentor().instrument(tracer_provider=provider)

    or let ``opentelemetry-instrument`` load it through the
    ``opentelemetry_instrumentor`` entry point.

    Besides the per-event spans and metrics, the app's ASGI callable is
    wrapped in the OpenTelemetry ASGI middleware, so HTTP requests (uploads,
    custom API routes) and the websocket connection get server spans and
    HTTP metrics as well.
    """

    def instrumentation_dependencies(self) -> Collection[str]:
        """Return the packages this instrumentor targets.

        Returns:
            The dependency specifiers for the instrumented package.
        """
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        """Turn on the Reflex trace points.

        Args:
            **kwargs: ``tracer_provider`` and ``meter_provider`` select the
                providers (default: the global ones). ``excluded_urls`` is a
                comma-separated list of URL patterns the ASGI middleware skips
                (default: ``OTEL_PYTHON_REFLEX_EXCLUDED_URLS``, else
                ``OTEL_PYTHON_EXCLUDED_URLS``, else ``/ping`` plus the compiled
                frontend's ``/assets/`` when the backend serves it; pass ``""``
                to exclude nothing).
                ``server_request_hook``, ``client_request_hook`` and
                ``client_response_hook`` are forwarded to the ASGI middleware.
        """
        # Imported here so `from reflex_otel import OtelPlugin` in rxconfig.py
        # stays cheap for CLI processes that never instrument.
        from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
        from opentelemetry.util.http import parse_excluded_urls

        tracer_provider = kwargs.get("tracer_provider")
        meter_provider = kwargs.get("meter_provider")
        excluded_urls = kwargs.get("excluded_urls")
        if excluded_urls is None:
            # A variable set to "" means "exclude nothing", like an empty kwarg.
            for name in _EXCLUDED_URLS_ENV_VARS:
                if (value := os.environ.get(name)) is not None:
                    excluded_urls = value
                    break

        def asgi_middleware(app: otel.ASGIApp) -> otel.ASGIApp:
            # Defaults resolve when the app builds its ASGI callable: only then
            # is it known whether the compiled frontend is mounted into it.
            urls = _default_excluded_urls() if excluded_urls is None else excluded_urls
            # opentelemetry-instrumentation-asgi < 0.56b0 stores a str verbatim
            # and then calls .url_disabled() on it, failing every request.
            if isinstance(urls, str):
                urls = parse_excluded_urls(urls)
            return OpenTelemetryMiddleware(
                app,
                excluded_urls=urls,
                server_request_hook=_server_request_hook(
                    kwargs.get("server_request_hook")
                ),
                client_request_hook=kwargs.get("client_request_hook"),
                client_response_hook=kwargs.get("client_response_hook"),
                tracer_provider=tracer_provider,
                meter_provider=meter_provider,
                exclude_spans=_ASGI_EXCLUDED_SPANS,
            )

        otel.enable(
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            asgi_middleware_factory=asgi_middleware,
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        """Turn off the Reflex trace points.

        Args:
            **kwargs: Ignored.
        """
        otel.disable()
