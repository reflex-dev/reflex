"""Minimal in-process repro of the documented reflex-otel env-var setup.

Runs the exact env from reflex-otel README / docs/api-reference/observability.md:
  OTEL_SERVICE_NAME / OTEL_TRACES_EXPORTER=otlp / OTEL_METRICS_EXPORTER=otlp /
  OTEL_EXPORTER_OTLP_ENDPOINT=<http endpoint>   (no OTEL_EXPORTER_OTLP_PROTOCOL)
in a venv that has exactly the documented `pip install` set.
"""

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

os.environ.setdefault("OTEL_SERVICE_NAME", "minapp")
os.environ.setdefault("OTEL_TRACES_EXPORTER", "otlp")
os.environ.setdefault("OTEL_METRICS_EXPORTER", "otlp")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:10283")
os.environ.pop("OTEL_EXPORTER_OTLP_PROTOCOL", None) if "--noproto" in sys.argv else None
if "--proto" in sys.argv:
    os.environ["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"

import reflex  # noqa: E402

assert "/envs/otel/" in reflex.__file__, reflex.__file__

from opentelemetry import trace  # noqa: E402
from reflex_base import otel as rb_otel  # noqa: E402
from reflex_otel import ReflexInstrumentor  # noqa: E402

print("reflex:", reflex.__file__)
print("before: enabled=", rb_otel.enabled, "provider=", type(trace.get_tracer_provider()).__name__)
ReflexInstrumentor().instrument()
print("after : enabled=", rb_otel.enabled, "provider=", type(trace.get_tracer_provider()).__name__)
print("asgi_middleware:", rb_otel.asgi_middleware)
tracer = trace.get_tracer("verify")
with tracer.start_as_current_span("probe") as s:
    print("span recording:", s.is_recording(), type(s).__name__)
try:
    trace.get_tracer_provider().force_flush()  # type: ignore[attr-defined]
    print("force_flush: ok")
except Exception as e:
    print("force_flush:", type(e).__name__, e)
