With OpenTelemetry tracing enabled, JSON log records (`REFLEX_LOG_JSON=true`) emitted inside a span now include its `trace_id` and `span_id`, so logs can be correlated with traces.
