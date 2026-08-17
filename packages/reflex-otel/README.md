# reflex-otel

OpenTelemetry instrumentation for the Reflex framework.

```python
from reflex_otel import ReflexInstrumentor

ReflexInstrumentor().instrument()
```

The package registers an `opentelemetry_instrumentor` entry point, so
`opentelemetry-instrument reflex run` enables it too (the auto-instrumentation
`sitecustomize` reaches the backend worker through the inherited `PYTHONPATH`).
Configure a tracer provider and a meter provider (for example with
`opentelemetry-sdk`) to export the data.

Reflex hot reload re-imports the app module in-process, so guard one-time SDK
setup:

```python
if not ReflexInstrumentor().is_instrumented_by_opentelemetry:
    trace.set_tracer_provider(provider)
    ReflexInstrumentor().instrument(tracer_provider=provider)
```

## What you get

Traces:

- One span per event handler run, named after the event: `SERVER` for events
  sent by the frontend (a new trace, or a child of the browser span when the
  event carries a `traceparent` field), `INTERNAL` for chained events, which
  are children of the span that enqueued them. `traceparent`/`tracestate`
  are consumed and never reach the handler.
- HTTP requests and the websocket connection are wrapped in the standard
  OpenTelemetry ASGI middleware (per-message websocket spans are off).

Metrics:

| Instrument | Type | Unit | Attributes |
| --- | --- | --- | --- |
| `reflex.event.duration` | histogram | s | `reflex.event.name`, `reflex.event.background`, `error.type` |
| `reflex.state.acquire.duration` | histogram | s | `reflex.event.name` |
| `reflex.websocket.message.size` | histogram | By | `network.io.direction` (`transmit`/`receive`); default `sio` only |
| `reflex.websocket.connections` | up-down counter | `{connection}` | |

Plus the ASGI middleware's `http.server.*` metrics.

## Options

`instrument()` accepts `tracer_provider`, `meter_provider`, `excluded_urls`
(comma-separated URL patterns skipped by the ASGI middleware; defaults to
`OTEL_PYTHON_REFLEX_EXCLUDED_URLS`, else `OTEL_PYTHON_EXCLUDED_URLS`, else
`/ping`; pass `""` to exclude nothing) and the ASGI hooks
`server_request_hook`, `client_request_hook`, `client_response_hook`.
Call `instrument()` before the app is served: `uninstrument()` turns the
framework trace points off again, but an ASGI middleware that was already
installed stays until the process restarts.
