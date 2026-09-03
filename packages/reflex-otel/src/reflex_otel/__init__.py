"""OpenTelemetry instrumentation for the Reflex framework."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from reflex_otel.plugin import OtelPlugin

if TYPE_CHECKING:
    from reflex_otel.instrumentor import ReflexInstrumentor


def __getattr__(name: str) -> Any:
    """Load the instrumentor on first use.

    ``rxconfig.py`` imports ``OtelPlugin`` in every CLI process; the instrumentor
    pulls in ``opentelemetry.instrumentation`` (and ``wrapt``), which only the
    backend needs.

    Args:
        name: The attribute being looked up.

    Returns:
        The instrumentor class.

    Raises:
        AttributeError: For any other name.
    """
    if name == "ReflexInstrumentor":
        from reflex_otel.instrumentor import ReflexInstrumentor

        return ReflexInstrumentor
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = ["OtelPlugin", "ReflexInstrumentor"]
