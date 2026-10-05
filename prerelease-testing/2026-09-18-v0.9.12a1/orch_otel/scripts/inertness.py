"""Check reflex_base.otel is inert without reflex-otel installed."""
import subprocess, sys, json, os

CODE = r'''
import sys, json
pre = [m for m in sys.modules if m.startswith("opentelemetry")]
import reflex
post = [m for m in sys.modules if m.startswith("opentelemetry")]
import reflex_base.otel as o
out = {
  "reflex_file": reflex.__file__,
  "otel_modules_after_import_reflex": post,
  "otel_modules_before": pre,
  "enabled": o.enabled,
  "asgi_middleware": repr(o.asgi_middleware),
  "reflex_otel_installed": False,
}
try:
    import reflex_otel  # noqa
    out["reflex_otel_installed"] = True
except ImportError:
    pass
# touching the module-level API modules must raise (never bound)
out["context_api_bound"] = hasattr(o, "context_api")
out["tracer_bound"] = hasattr(o, "_tracer")
# nullcontext path
with o.span("x") as s:
    out["span_returns"] = repr(s)
with o.compile_span("t", False) as s:
    out["compile_span_returns"] = repr(s)
out["capture_context"] = repr(o.capture_context())
o.attach_context(None)
o.record_message_size(10, "transmit")
o.record_connection(1)
print("JSON:" + json.dumps(out))
'''

for env in sys.argv[1:]:
    py = f"{env}/bin/python"
    r = subprocess.run([py, "-c", CODE], capture_output=True, text=True, cwd="/tmp")
    print("=" * 70)
    print(env)
    print(r.stdout.strip()[:4000])
    if r.returncode:
        print("STDERR", r.stderr[-3000:])
