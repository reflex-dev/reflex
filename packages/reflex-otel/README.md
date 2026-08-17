# reflex-otel

OpenTelemetry instrumentation for the Reflex framework.

```python
from reflex_otel import ReflexInstrumentor

ReflexInstrumentor().instrument()
```

The package registers an `opentelemetry_instrumentor` entry point, so
`opentelemetry-instrument reflex run` enables it automatically. Configure a
tracer provider (for example with `opentelemetry-sdk`) to export the spans.
