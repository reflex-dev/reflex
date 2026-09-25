# reflex-bench

Macro benchmarks for Reflex. `reflex-bench` drives benchmarks through one command
line interface, stores every raw sample with the machine it ran on, and compares
results with statistics that say "inconclusive" instead of guessing.

The CLI is the only code path: CI runs the same commands and only adds output
targets. The harness never imports the reflex under test; benchmarks reach it
through subprocesses, HTTP, sockets and a browser. This package is used inside
this repository only and is never published.

```console
$ uv run reflex-bench list --suite selftest
$ uv run reflex-bench run --suite selftest
$ uv run reflex-bench run selftest.noise --param shift=1.2 --baseline 0001
$ uv run reflex-bench compare base.json head.json --format md
$ uv run reflex-bench doctor
$ uv run reflex-bench export result.json --to bmf
```

## Commands

| Command | What it does |
| --- | --- |
| `list [FILTER...] [--suite NAME]` | Benchmarks with their parameters, kind, metrics, suites and estimated duration. |
| `run [FILTER...]` | Runs benchmarks, prints the result table, autosaves the result and optionally compares it with a baseline. |
| `show FILE [--samples]` | One result in detail, optionally with every raw sample. |
| `compare BASE HEAD [--format term\|md\|json]` | Compares two results; `json` prints the annotated head result. |
| `doctor` | Machine checks that affect measurement noise, with fix hints. |
| `export FILE --to md\|bmf [-o OUT]` | Pull request markdown or [Bencher Metric Format](https://bencher.dev/docs/reference/bencher-metric-format/). |

`FILTER` is a glob on the benchmark id (`lifecycle.*`, `*.warm`). Suites are named
selections: `smoke`, `pr`, `daily`, `selftest` and `all` (every benchmark except
the self-tests). Self-tests only run when asked for, with `--suite selftest` or a
filter starting with `selftest`.

Main `run` options (every effective value is printed in the header and stored in
the result's `policy` block):

| Option | Default | |
| --- | --- | --- |
| `--runs N` | automatic | Fixed number of timed runs. |
| `--min-runs`, `--max-runs`, `--min-time` | 10, max(30, min-runs), 30 s | The automatic run count (below). |
| `--warmup N` | per benchmark | Untimed runs, stored but excluded from statistics. |
| `--timeout SECONDS` | per benchmark | Deadline of each `prepare`, `sample` and `conclude` call. |
| `--param KEY=VALUE` | | Restricts a parameter to one value, or sets a new value or a hidden parameter. |
| `--baseline NAME\|FILE\|NUMBER` | | Compares with a file, a named baseline or an autosave number (`0041`). |
| `--save/--no-save`, `--save-as NAME`, `--json FILE` | autosave | Where to store the result. |
| `--threshold PCT`, `--alpha FLOAT` | 3, 0.01 | Practical threshold and significance level of verdicts. |
| `--fail-on regression\|never`, `--fail-on-inconclusive` | never locally, regression when `CI=true` | Exit codes 2 and 3. |
| `--smoke` | | One run, no warmup, no statistics: checks that each benchmark works. |
| `--ndjson` | | Progress events as JSON lines on stdout; human output moves to stderr. |
| `--seed INT` | random | Seeds each benchmark's RNG and the bootstrap; always recorded. |
| `--keep` | | Keeps each benchmark's work directory. |
| `--kind` | `local` or `ci` | The run kind recorded in the result (`pr`, `daily`, `backfill`, `aa`). |

Exit codes: `0` ok, `1` harness error (including usage errors, every benchmark
failing, or nothing to compare), `2` regression with `--fail-on regression`, `3`
inconclusive result with `--fail-on-inconclusive`. A benchmark that fails or
times out is reported with its status and does not stop the run; when comparing,
one that fails or times out in head but not in base (or is new) is a regression.

With `CI=true` the output is plain (no colors, no live progress, one line per
finished benchmark) and `--fail-on` defaults to `regression`. Nothing else changes.

## Writing a benchmark

Benchmarks live in modules of `reflex_bench.suites`; every module there is
imported on discovery.

```python
import time

from reflex_bench.registry import Metric, benchmark


@benchmark(
    id="selftest.sleep",
    suites=("selftest",),
    kind="time",  # time | startup | rate | latency | peakmem | track
    params={"ms": [10, 50]},  # cartesian product: selftest.sleep[ms=10], [ms=50]
    metrics={"wall": Metric(unit="s", direction="lower")},
    warmup=1,
    timeout=60,  # seconds per prepare/sample/conclude call
    estimate=5,  # rough seconds per sample, for `list`
    min_version=None,  # e.g. "0.9.8": older subjects report "unsupported"
)
class Sleep:
    """Sleep for a fixed time; checks the timing pipeline."""

    def setup_cache(self, ctx): ...  # once per subject and parameter set
    def setup(self, ctx): ...  # once per instance
    def prepare(self, ctx): ...  # before each sample, untimed
    def sample(self, ctx):  # one sample
        time.sleep(ctx.params["ms"] / 1000)

    def conclude(self, ctx): ...  # after each sample, untimed
    def cleanup(self, ctx): ...  # once at the end
```

Every hook except `sample` is optional; `conclude` and `cleanup` always run, also
after a failure or a timeout. Further `@benchmark` arguments:
`hidden_params={"name": default}` for parameters that are passed to hooks but are
not part of the name or the series key, and `setup_timeout` (600 s) for
`setup_cache`, `setup` and `cleanup`.

**Metrics** are declared with `Metric(unit, direction, assume="nothing",
description="")`. Values are stored in SI base units (`s`, `B`, `ev/s`, `1` for
counts); scaling to ms or MB only happens on display. `assume="exact"` marks a
deterministic value: one run is enough and any variance is reported.

**`sample(ctx)`** returns `None`, a dict of metric values, or
`SampleResult(values, extra)` whose JSON-serializable `extra` is stored with the
sample. The harness always times the call; a declared `wall` metric that
`sample()` does not return is filled with that duration. Returning an undeclared
metric, or leaving out a declared one, fails the benchmark.

**`ctx`** is a `reflex_bench.context.Context`: `subject` (the reflex under test:
`python`, `reflex_version`, `commit`, `dirty`, ...), `params` (hidden ones
included), `workdir` (fresh per instance, removed after `cleanup` unless
`--keep`), `cache_dir` (persistent per subject commit, benchmark id and
parameter set, for `setup_cache` results; the hook decides what to reuse),
`env` (the environment for subprocesses: telemetry and update checks off,
`NO_COLOR`, `PYTHONUNBUFFERED`, `PYTHONHASHSEED=0`, granian), `rng` (seeded),
`log` and `arm`.

All hooks of an instance run on one worker thread, so thread-bound resources
(such as a sync Playwright browser) work across hooks. A hook that misses its
deadline ends the instance with status `timeout`; the stuck thread is abandoned
and the remaining teardown hooks run on a fresh one (as they do after Ctrl-C),
so `conclude` should kill whatever `sample` started. A hook still running a few
seconds after teardown keeps the work directory and skips the benchmark's
remaining parameter sets. `reflex_bench.registry.Instance` exposes the hooks as
zero-argument methods and `reflex_bench.scheduler.make_context` builds the same
context as the scheduler, for callers other than the scheduler.

## How samples are taken

After the warmup runs, the first timed sample decides the run count (hyperfine's
rule): `clamp(max(min_runs, ceil(min_time / first_sample)), min_runs, max_runs)`.
`--runs` fixes it; benchmarks whose metrics are all exact take one run.

Each metric gets a summary per arm: median with an exact order-statistic 95 %
confidence interval (needs at least 6 samples), mean, standard deviation,
quartiles, MAD, coefficient of variation and Tukey outlier counts. Outliers are
never removed. Warnings flag a CV of 10 % or more, a maximum 50 % above or a
minimum 50 % below the median, a slow first sample (modified z-score above 14.8:
raise `--warmup`) and severe outliers.

## Comparisons

Entries are paired by id, parameters and dims, and compared only when their full
series key matches: id, parameters, dims, machine profile, fixture content hash
and benchmark version (a hash of the benchmark's source). `compare --force`
overrides that. For each metric:

- the change is `median(head) / median(base) - 1`, with a percentile bootstrap
  confidence interval (seeded, 10,000 resamples); when the base median is not
  positive (or too many resampled base medians are not), the change is the
  absolute `median(head) - median(base)` in the metric's unit (`mode: absolute`),
  and its verdicts need the whole CI on one side of zero instead of past the
  threshold;
- a two-sided Mann-Whitney U test gives the p-value (exact without ties up to
  20 samples per side, normal approximation otherwise), and Holm's correction
  runs across all tested metrics of the comparison;
- **regressed** or **improved** needs an adjusted p-value below alpha *and* the
  whole CI beyond the threshold; **no change** needs the whole CI within the
  threshold; everything else, including too few samples for the test to reach
  alpha or for a CI, is **inconclusive**, with a rough estimate of the runs per
  side that would decide it (up to 200);
- exact metrics compare values directly against the threshold.

The verdicts are written into the head result (`comparison` per metric and
`compared_to` at the top), so `show` and `export --to md` can render them later.

## Results

One JSON document per invocation, schema `reflex-bench/1` (see
`reflex_bench/schema.py`): `schema`, `tool`, `invocation` (argv, times, mode,
kind, CI run, seed), `subjects` (arm `A`, later also `B`), `machine` (with
`profile_id`), optional `fixture`, `policy` and `benchmarks`. Each benchmark
entry keeps its status, error and traceback tail, every raw sample per arm
(warmups included and marked in `sample_meta`), per-sample extra data, and the
derived summaries, warnings and comparisons. Documents are validated on load and
before every write.

Local storage lives in `.reflex-bench/` at the root of the git checkout (or the
working directory), or in `$REFLEX_BENCH_HOME`:

```
results/<profile_id>/<NNNN>_<short sha>[_dirty]_<UTC timestamp>.json
results/<profile_id>/.claims/<NNNN>
baselines/<profile_id>/<name>.json
cache/<commit>[-dirty]/<benchmark id>/<params hash>/
```

The cache is keyed by the subject's commit (its spec when the commit is
unknown).

The machine profile id is `<os>-<arch>-<cpu model>-py<major.minor>`, for example
`linux-x86_64-ryzen-9-7950x-py3.12`; `REFLEX_BENCH_PROFILE` overrides it (other
characters than letters, digits, `.`, `_` and `-` become `-`). Results from
different profiles are never compared.
