# Observability (OpenTelemetry)

Reflex has built-in [OpenTelemetry](https://opentelemetry.io) trace points and
metrics. They are inert (one boolean check) until you install the optional
`reflex-otel` package and turn them on. Any OpenTelemetry backend works:
Jaeger, Grafana Tempo, SigNoz, Honeycomb, Datadog, ...

## Backend: install and enable

```bash
pip install reflex-otel opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

Enable the Reflex instrumentation at import time of your app module:

```python
from reflex_otel import ReflexInstrumentor

ReflexInstrumentor().instrument()
```

A second call is a silent no-op, so the line needs no guard. Configure the
SDK through the standard environment: when `OTEL_TRACES_EXPORTER` or
`OTEL_METRICS_EXPORTER` is set and no SDK provider has been installed yet,
`instrument()` configures `opentelemetry-sdk` from the `OTEL_*` variables,
exactly as `opentelemetry-instrument` would:

```bash
OTEL_SERVICE_NAME=my_app OTEL_TRACES_EXPORTER=otlp OTEL_METRICS_EXPORTER=otlp \
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318 reflex run
```

To build the providers yourself, pass them instead:
`instrument(tracer_provider=..., meter_provider=...)`, from a module that is
imported once (test harnesses re-import the app module, and the SDK warns
when a provider is overridden).

`ReflexInstrumentor` also registers the standard `opentelemetry_instrumentor`
entry point, so `opentelemetry-instrument reflex run` enables it with no code.

### What is traced

- One span per event handler run, named after the event, with
  `reflex.event.name`, `reflex.event.txid`, `reflex.event.background`,
  `session.id` and `code.function.name`. Exceptions are recorded on the span
  with their message and stack trace. Events sent by the browser are
  `CONSUMER` spans: a new trace, or a child of the browser's `PRODUCER` span
  when the frontend plugin (below) is active. Only string `traceparent` and
  `tracestate` fields are read from an event; the client's sampled flag is
  honoured by a parent-based sampler, so set `OTEL_TRACES_SAMPLER=always_on`
  (or a `ParentBased` sampler with explicit remote decisions) to keep
  sampling on the server.
- Events returned by a handler (chained events) are `INTERNAL` children of the
  span that produced them.
- HTTP requests and the websocket connection get spans and `http.server.*`
  metrics from the OpenTelemetry ASGI middleware, using the stable HTTP
  semantic conventions (`OTEL_SEMCONV_STABILITY_OPT_IN=http` is set unless
  you chose a value). The frontend's `/ping` poll and, when the backend
  serves the compiled frontend, its `/assets/` are excluded by default
  (`excluded_urls=` or `OTEL_PYTHON_REFLEX_EXCLUDED_URLS`).
- Each app compile is a `reflex.compile` span with the stages
  (`reflex.compile.pages`, `reflex.compile.write`, ...) as children.

### What leaves the process

Event and handler names, a pseudonymous `session.id` (a truncated SHA-256 of
the client token, never the token itself; the token is also redacted from
the websocket span's request attributes), exception types, messages and
stack traces of failed handlers, and the ASGI middleware's request
attributes. Event payloads and state are never recorded.

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

- sends a W3C `traceparent` with every event and file upload, so each user
  interaction is one trace: browser span → backend event span → chained
  events;
- reports web vitals (`web_vital.LCP`, `CLS`, `INP`, `FCP`, `TTFB`) as spans;
- with `render_timing=True`, reports React commits as `react.render` spans
  (one per commit; uses the `react-dom/profiling` build);
- records `socket.connect` / `socket.disconnect` spans.

`endpoint` is required to export: a URL the browser can reach that accepts
OTLP/HTTP (CORS). It has no default and the backend's `OTEL_EXPORTER_OTLP_*`
variables are not consulted, since they usually name a collector on a private
network. Without it the plugin installs no exporter and browser spans are
dropped. The first failed export on a page is reported through the app's
`frontend_exception_handler`, so a rejected collector shows up in the backend
terminal as an `OtelExportError`. `service_name` defaults to `<app_name>-frontend`. `headers` are
compiled into the public bundle, so never put secrets in them. `sample_rate`
(default `1.0`) samples browser traces at the root. Only sampled browser spans
send a `traceparent`, so the backend joins those traces and samples every
other event on its own; a low browser rate does not cap backend tracing.
