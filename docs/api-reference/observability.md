# Observability (OpenTelemetry)

Reflex has built-in [OpenTelemetry](https://opentelemetry.io) trace points and
metrics. They are inert (one boolean check) until you install the optional
`reflex-otel` package and turn them on. Any OpenTelemetry backend works:
Jaeger, Grafana Tempo, SigNoz, Honeycomb, Datadog, ...

## Backend: install and enable

```bash
pip install reflex-otel opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

Configure the SDK as usual and enable the Reflex instrumentation once, at
import time of your app module:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from reflex_otel import ReflexInstrumentor

if not ReflexInstrumentor().is_instrumented_by_opentelemetry:
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    ReflexInstrumentor().instrument(tracer_provider=provider)
```

Guard the setup as shown: Reflex hot reload re-imports the app module, and
`set_tracer_provider()` / `instrument()` warn when called twice.

`ReflexInstrumentor` also registers the standard `opentelemetry_instrumentor`
entry point, so `opentelemetry-instrument reflex run` enables it with no code.

### What is traced

- One span per event handler run, named after the event, with
  `reflex.event.name`, `reflex.event.txid`, `reflex.event.background`,
  `session.id` and `code.function.name`. Exceptions are recorded on the span.
  Events sent by the browser are `SERVER` spans: a new trace, or a child of the
  browser span when the frontend plugin (below) is active.
- Events returned by a handler (chained events) are `INTERNAL` children of the
  span that produced them.
- HTTP requests and the websocket connection get spans and `http.server.*`
  metrics from the OpenTelemetry ASGI middleware.
- Each app compile is a `reflex.compile` span with the stages
  (`reflex.compile.pages`, `reflex.compile.write`, ...) as children.

### Metrics

| Instrument | Type | Unit | Attributes |
| --- | --- | --- | --- |
| `reflex.event.duration` | histogram | s | `reflex.event.name`, `reflex.event.background`, `error.type` |
| `reflex.state.acquire.duration` | histogram | s | `reflex.event.name` |
| `reflex.websocket.message.size` | histogram | By | `network.io.direction` |
| `reflex.websocket.connections` | up-down counter | `{connection}` | |

Pass `meter_provider=` to `instrument()` to export them (defaults to the global
meter provider).

## Frontend: browser traces

Add the plugin to your config to trace the browser as well:

```python
# rxconfig.py
import reflex as rx
from reflex_otel import OtelPlugin

config = rx.Config(
    app_name="my_app",
    plugins=[OtelPlugin(endpoint="https://collector.example.com/v1/traces")],
)
```

The compiled frontend then

- sends a W3C `traceparent` with every event, so each user interaction is one
  trace: browser span → backend event span → chained events;
- reports web vitals (`web_vital.LCP`, `CLS`, `INP`, `FCP`, `TTFB`) as spans;
- with `render_timing=True`, reports React commits as `react.render` spans
  (one per commit; uses the `react-dom/profiling` build);
- records `socket.connect` / `socket.disconnect` spans.

`endpoint` defaults to `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, then
`OTEL_EXPORTER_OTLP_ENDPOINT` + `/v1/traces`, then
`http://localhost:4318/v1/traces`; it must accept OTLP/HTTP from the browser
(CORS). The first failed export on a page is reported through the app's
`frontend_exception_handler`, so a rejected collector shows up in the backend
terminal as an `OtelExportError`. `service_name` defaults to `<app_name>-frontend`. `headers` are
compiled into the public bundle, so never put secrets in them. `sample_rate`
(default `1.0`) samples browser traces at the root. Only sampled browser spans
send a `traceparent`, so the backend joins those traces and samples every
other event on its own; a low browser rate does not cap backend tracing.
