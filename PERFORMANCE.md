# Performance benchmark guide

Reflex uses separate performance tiers because deterministic CPU work, asynchronous wall time, service load, memory, compiler lifecycle, and browser behavior have different noise and cost profiles.

## Benchmark tiers

| Tier | Location | Runs | Purpose |
| --- | --- | --- | --- |
| Deterministic CPU | `tests/benchmarks/` | Every pull request | CodSpeed regression detection and flamegraphs |
| Component wall time | `tests/performance/` | Manual | Event-loop, task, queue, Redis, and allocation behavior |
| Load and lifecycle | `tests/performance/` | Manual | Tail latency, saturation, compiles, hot reload, browser metrics |

Do not add sleep, network, filesystem, browser, or subprocess timings to a CodSpeed instrumentation benchmark. Put those in a wall-time suite and emit a versioned JSON report.

## Naming and fixture rules

- Name benchmarks after the user-visible path they protect, not an implementation detail.
- Separate cold and warm paths.
- Keep setup outside the measured call unless setup is the behavior being measured.
- Use `time.perf_counter_ns()` for wall-time observations.
- Use explicit warmup and measurement counts.
- Batch sub-microsecond operations.
- Preserve raw observations in scheduled-suite artifacts.
- Include small representative and stress cases, but reserve full parameter matrices for scheduled runs.
- Validate correctness—event ordering, final state, update count, errors—inside every performance scenario.

Shared fixtures and reporting helpers live in `tests/benchmarks/support/`. Scheduled reports use schema version 1 and include the commit, branch, Python, OS, CPU, parameters, raw observations, latency summaries, and suite-specific metrics.

## Commands

```console
uv run pytest tests/benchmarks --codspeed
uv run pytest tests/performance -m performance --run-performance
```

Individual scheduled suites are controlled by explicit command-line options and environment variables documented in their tests and workflows. They are excluded from ordinary unit and integration discovery.

## Regression policy

Thresholds become merge-blocking only after at least 20 comparable baseline runs establish their variance and a benchmark owner accepts the budget. Initial review levels are:

- More than 5% deterministic CodSpeed CPU regression when statistically supported.
- More than 10% stable component wall-time regression.
- More than 15% p95 or p99 load latency regression at equal offered load.
- More than 10% throughput loss at the established latency objective.
- Any event-ordering failure, lost update, orphan task, or monotonic retained-memory growth.

Use an absolute floor as well as a percentage. Environment mismatches make comparisons informational unless explicitly approved.

## Adding or changing a benchmark

1. State the behavior and regression it protects.
2. Choose the correct tier.
3. Add correctness assertions.
4. Record parameters, warmups, iterations, and environment metadata.
5. Run the focused benchmark and its support tests.
6. Review variance before adding a threshold.
7. Update this guide if the suite, schema, or policy changes.

Benchmark fixtures are reviewed quarterly. Remove tests that no longer represent supported behavior, but preserve historical benchmark names when a time series remains meaningful.
