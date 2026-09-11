"""Programmatic checks of the ReflexInstrumentor API surface."""
import json, os, subprocess, sys

PY = sys.argv[1]

CASES = {
"second_instrument_noop": r'''
from opentelemetry.sdk.trace import TracerProvider
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
p1, p2 = TracerProvider(), TracerProvider()
i = ReflexInstrumentor()
i.instrument(tracer_provider=p1)
t1 = o._tracer
i.instrument(tracer_provider=p2)          # must be a no-op
t2 = o._tracer
print("RESULT", json.dumps({"enabled": o.enabled, "same_tracer": t1 is t2,
      "is_instrumented": i.is_instrumented_by_opentelemetry}))
''',
"uninstrument_then_instrument": r'''
from opentelemetry.sdk.trace import TracerProvider
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
i = ReflexInstrumentor()
i.instrument(tracer_provider=TracerProvider())
a = (o.enabled, o.asgi_middleware is not None)
i.uninstrument()
b = (o.enabled, o.asgi_middleware is not None, repr(o._event_duration))
i.instrument(tracer_provider=TracerProvider())
c = (o.enabled, o.asgi_middleware is not None)
print("RESULT", json.dumps({"after_instrument": a, "after_uninstrument": b, "after_reinstrument": c}))
''',
"otel_sdk_disabled": r'''
import os
os.environ["OTEL_SDK_DISABLED"] = "true"
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
ReflexInstrumentor().instrument()
print("RESULT", json.dumps({"enabled": o.enabled, "asgi": repr(o.asgi_middleware)}))
''',
"excluded_urls_empty_string": r'''
from opentelemetry.sdk.trace import TracerProvider
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
ReflexInstrumentor().instrument(tracer_provider=TracerProvider(), excluded_urls="")
mw = o.asgi_middleware(lambda *a: None)
print("RESULT", json.dumps({"excluded": repr(getattr(mw, "excluded_urls", None))}))
''',
"excluded_urls_default": r'''
from opentelemetry.sdk.trace import TracerProvider
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
ReflexInstrumentor().instrument(tracer_provider=TracerProvider())
mw = o.asgi_middleware(lambda *a: None)
print("RESULT", json.dumps({"excluded": repr(getattr(mw, "excluded_urls", None))}))
''',
"env_excluded_urls": r'''
import os
os.environ["OTEL_PYTHON_REFLEX_EXCLUDED_URLS"] = "/healthz,/ping"
from opentelemetry.sdk.trace import TracerProvider
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
ReflexInstrumentor().instrument(tracer_provider=TracerProvider())
mw = o.asgi_middleware(lambda *a: None)
print("RESULT", json.dumps({"excluded": repr(getattr(mw, "excluded_urls", None))}))
''',
"semconv_optin_default": r'''
import os
import reflex_otel.instrumentor  # noqa
print("RESULT", json.dumps({"OTEL_SEMCONV_STABILITY_OPT_IN": os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN")}))
''',
"semconv_optin_respects_user": r'''
import os
os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "http/dup"
import reflex_otel.instrumentor  # noqa
print("RESULT", json.dumps({"OTEL_SEMCONV_STABILITY_OPT_IN": os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN")}))
''',
"plugin_sample_rate_validation": r'''
from reflex_otel import OtelPlugin
out = {}
for v in (-0.1, 0, 0.5, 1, 1.5):
    try:
        OtelPlugin(sample_rate=v); out[str(v)] = "ok"
    except ValueError as e:
        out[str(v)] = f"ValueError: {e}"
print("RESULT", json.dumps(out))
''',
"exporter_env_without_sdk_warns": r'''
import logging, os
logging.basicConfig(level=logging.DEBUG)
os.environ["OTEL_TRACES_EXPORTER"] = "otlp"
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
from opentelemetry import trace
ReflexInstrumentor().instrument()
print("RESULT", json.dumps({"enabled": o.enabled, "provider": type(trace.get_tracer_provider()).__name__}))
''',
"remote_context_hostile_input": r'''
from opentelemetry.sdk.trace import TracerProvider
from reflex_otel import ReflexInstrumentor
import reflex_base.otel as o
ReflexInstrumentor().instrument(tracer_provider=TracerProvider())
out = {}
for name, carrier in {
    "bad_types": {"traceparent": 123, "tracestate": ["x"], "baggage": "k=v"},
    "garbage": {"traceparent": "not-a-traceparent"},
    "valid": {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"},
    "baggage_only": {"baggage": "secret=1"},
}.items():
    from opentelemetry import trace, baggage
    with o.remote_context(carrier):
        sc = trace.get_current_span().get_span_context()
        out[name] = {"trace_id": format(sc.trace_id, "032x"), "remote": sc.is_remote,
                     "baggage": dict(baggage.get_all())}
print("RESULT", json.dumps(out))
''',
}

for name, code in CASES.items():
    src = "import json\n" + code
    r = subprocess.run([PY, "-c", src], capture_output=True, text=True, cwd="/tmp")
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT")]
    print("=" * 60)
    print(name)
    print("  ", line[0][7:] if line else f"NO RESULT rc={r.returncode}")
    warn = [l for l in (r.stderr or "").splitlines() if l.strip()]
    if warn:
        print("   stderr:", " | ".join(warn[-4:])[:600])
