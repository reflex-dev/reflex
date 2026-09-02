Stop re-sending a cached computed var whose recomputed value is unchanged, and stop re-walking the computed var dependency graph on every write within one event handler.
