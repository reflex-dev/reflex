# reflex-otel

OpenTelemetry instrumentation for the Reflex framework.

```python
from reflex_otel import ReflexInstrumentor

ReflexInstrumentor().instrument()
```

The package registers an `opentelemetry_instrumentor` entry point, so
`opentelemetry-instrument reflex run` enables it automatically. Configure a
tracer provider and a meter provider (for example with `opentelemetry-sdk`)
to export the data.

## What you get

Traces:

- One `SERVER` span per event handler run, named after the event. Chained
  events are children of the span that enqueued them. An event sent by the
  frontend with a `traceparent` field continues that trace; otherwise it
  starts a new one.
- HTTP requests and the websocket connection are wrapped in the standard
  OpenTelemetry ASGI middleware (per-message websocket spans are off).

Metrics:

| Instrument | Type | Unit | Attributes |
| --- | --- | --- | --- |
| `reflex.event.duration` | histogram | s | `reflex.event.name`, `reflex.event.background`, `error.type` |
| `reflex.state.acquire.duration` | histogram | s | `reflex.event.name` |
| `reflex.websocket.message.size` | histogram | By | `network.io.direction` (`transmit`/`receive`) |
| `reflex.websocket.connections` | up-down counter | `{connection}` | |

Plus the ASGI middleware's `http.server.*` metrics.

## Options

`instrument()` accepts `tracer_provider`, `meter_provider`, `excluded_urls`
(comma-separated URL patterns skipped by the ASGI middleware; defaults to the
`OTEL_PYTHON_REFLEX_EXCLUDED_URLS` environment variable) and the ASGI hooks
`server_request_hook`, `client_request_hook`, `client_response_hook`.
