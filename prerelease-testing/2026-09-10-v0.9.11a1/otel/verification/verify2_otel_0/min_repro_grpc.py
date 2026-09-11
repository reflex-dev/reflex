"""Same documented env, but with the FULL opentelemetry-exporter-otlp installed.

Shows what the docs' example does when the grpc exporter IS available: the
`otlp` alias resolves to otlp_proto_grpc and speaks gRPC at the HTTP port
:4318 (here :10283) from the very same example.
"""

import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
os.environ.update(
    OTEL_SERVICE_NAME="myapp",
    OTEL_TRACES_EXPORTER="otlp",
    OTEL_METRICS_EXPORTER="otlp",
    OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:10283",
    OTEL_BSP_SCHEDULE_DELAY="500",
)
import reflex  # noqa: E402

assert "/envs/verify2_otel_0/" in reflex.__file__, reflex.__file__
from opentelemetry import trace  # noqa: E402
from reflex_base import otel as rb_otel  # noqa: E402
from reflex_otel import ReflexInstrumentor  # noqa: E402
from importlib.metadata import entry_points  # noqa: E402

print("entry points:", sorted(e.name for e in entry_points(group="opentelemetry_traces_exporter")))
ReflexInstrumentor().instrument()
print("enabled=", rb_otel.enabled, "provider=", type(trace.get_tracer_provider()).__name__)
with trace.get_tracer("verify").start_as_current_span("probe") as s:
    print("span recording:", s.is_recording())
import time  # noqa: E402
time.sleep(3)
trace.get_tracer_provider().force_flush()  # type: ignore[attr-defined]
print("flushed")
