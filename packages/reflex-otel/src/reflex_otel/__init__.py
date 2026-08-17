"""OpenTelemetry instrumentation for the Reflex framework."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from reflex_base import otel

_instruments = ("reflex-base >= 0.9.7.post45.dev0",)


class ReflexInstrumentor(BaseInstrumentor):
    """Enable the trace points built into the Reflex runtime.

    Usage::

        ReflexInstrumentor().instrument(tracer_provider=provider)

    or let ``opentelemetry-instrument`` load it through the
    ``opentelemetry_instrumentor`` entry point.
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
            **kwargs: ``tracer_provider`` selects the provider; defaults to the global one.
        """
        otel.enable(tracer_provider=kwargs.get("tracer_provider"))

    def _uninstrument(self, **kwargs: Any) -> None:
        """Turn off the Reflex trace points.

        Args:
            **kwargs: Ignored.
        """
        otel.disable()
