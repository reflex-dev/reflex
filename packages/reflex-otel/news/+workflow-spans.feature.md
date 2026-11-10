`ReflexInstrumentor().instrument()` also turns on the trace points of `reflex-workflow` when it is installed: one `CONSUMER` span per step attempt, linked to the span that scheduled it.
