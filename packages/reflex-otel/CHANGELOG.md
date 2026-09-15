

<!-- towncrier release notes start -->

## v0.1.0 (2026-09-11)

### Features

- Add the `reflex-otel` package: an OpenTelemetry instrumentor that turns on the framework's built-in trace points and metrics (one span per event handler run, chained events parented under the enqueuing span, frontend `traceparent` propagation, event/state/websocket metrics, compile spans) and wraps the ASGI app in the OpenTelemetry ASGI middleware. `OtelPlugin(endpoint=...)` adds browser tracing (a `traceparent` on sampled events and uploads, web vitals, React render timing) to the compiled frontend; without an endpoint nothing is exported. Failed browser exports (for example a collector without CORS) are reported through the app's `frontend_exception_handler`. ([#6227](https://github.com/reflex-dev/reflex/issues/6227))

### Documentation

- Correct the environment-variable setup example to select HTTP/protobuf for the installed OTLP HTTP exporter. ([#7086](https://github.com/reflex-dev/reflex/issues/7086))
