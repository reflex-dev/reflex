"""OpenTelemetry instrumentation for the Reflex framework."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any, Literal

from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.util.http import get_excluded_urls
from reflex_base import otel

_instruments = ("reflex-base >= 0.9.7.post45.dev0",)

# Per-message websocket spans are noise; Reflex emits one span per event instead.
_ASGI_EXCLUDED_SPANS: list[Literal["receive", "send"]] = ["receive", "send"]


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
                (default: ``OTEL_PYTHON_REFLEX_EXCLUDED_URLS``).
                ``server_request_hook``, ``client_request_hook`` and
                ``client_response_hook`` are forwarded to the ASGI middleware.
        """
        tracer_provider = kwargs.get("tracer_provider")
        meter_provider = kwargs.get("meter_provider")
        excluded_urls = kwargs.get("excluded_urls")

        def asgi_middleware(app: Any) -> Any:
            return OpenTelemetryMiddleware(
                app,
                excluded_urls=(
                    get_excluded_urls("REFLEX")
                    if excluded_urls is None
                    else excluded_urls
                ),
                server_request_hook=kwargs.get("server_request_hook"),
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
