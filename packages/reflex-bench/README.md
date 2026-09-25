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
$ uv run reflex-bench run --reflex 0.8.23 --suite selftest
$ uv run reflex-bench ab --base git:main --head workspace --suite selftest
$ uv run reflex-bench compare base.json head.json --format md
$ uv run reflex-bench doctor
$ uv run reflex-bench export result.json --to bmf
$ uv run reflex-bench subjects list
```

## Commands

| Command | What it does |
| --- | --- |
| `list [FILTER...] [--suite NAME]` | Benchmarks with their parameters, kind, metrics, suites and estimated duration. |
| `run [FILTER...] [--reflex SPEC]` | Runs benchmarks against one reflex, prints the result table, autosaves the result and optionally compares it with a baseline. |
| `ab --base SPEC --head SPEC [FILTER...]` | Measures two reflexes in alternation on this machine and compares them ([A/B runs](#ab-runs)). |
| `show FILE [--samples]` | One result in detail, optionally with every raw sample. |
| `compare BASE HEAD [--format term\|md\|json]` | Compares two results; `json` prints the annotated head result. |
| `doctor` | Machine checks that affect measurement noise, with fix hints. |
| `export FILE --to md\|bmf [-o OUT]` | Pull request markdown or [Bencher Metric Format](https://bencher.dev/docs/reference/bencher-metric-format/). |
| `subjects list` | The cached [subject](#subjects) venvs: spec, Python, key, size and last use. |
| `subjects prune [--older-than 30d]` | Deletes venvs not used for that long (`30d`, `12h`, `90m`), leftovers of interrupted builds and git worktrees no venv uses. |

`FILTER` is a glob on the benchmark id (`lifecycle.*`, `*.warm`). Suites are named
selections: `smoke`, `pr`, `daily`, `selftest` and `all` (every benchmark except
the self-tests). Self-tests only run when asked for, with `--suite selftest` or a
filter starting with `selftest`.

Main `run` options (every effective value is printed in the header and stored in
the result's `policy` block):

| Option | Default | |
| --- | --- | --- |
| `--reflex SPEC` | `workspace` | The reflex to measure (see [Subjects](#subjects)). |
| `--python VERSION` | the harness's | The Python of subject venvs (major.minor of the interpreter running reflex-bench, which the workspace runs on). |
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

## Subjects

The reflex under test, `--reflex SPEC` (`--base` and `--head` for `ab`):

| SPEC | Meaning |
| --- | --- |
| `workspace` (default) | This checkout, in the harness's own environment. |
| `0.8.23`, any PEP 440 version | `reflex==<version>` from PyPI. |
| `git:<ref>` | A commit, branch or tag of the current repository, e.g. `git:main`, `git:v0.9.11`. |
| `path:<dir>` | Another local checkout, e.g. `path:../reflex-wt-other`. |

Every spec but `workspace` runs in its own virtualenv, `<home>/venvs/<key>/`,
created with `uv venv --relocatable --python <--python>` and never containing
the harness. The key is the first 16 hex digits of the SHA-256 of the subject's
identity (the version; the commit of a git ref; the absolute path, commit and
dirty flag of a path), the `--python` value and the harness's extra subject
requirements (none so far). A venv is built in a temporary directory and renamed
into place when complete, under a lock, so a half-built venv is never reused and
concurrent runs build it once. A `path:` subject with uncommitted changes (or
outside git) is rebuilt every time. The build happens before anything is timed
and says what it does (`building venv for reflex 0.8.23 (py3.12)…`, `reusing
venv …`).

A `git:` subject is checked out as a detached git worktree in
`<home>/src/<commit>/` (reused when present; a worktree keeps the tags the
packages' versions are computed from). A checkout with a `uv.lock` is installed
with the dependency set of `uv export --frozen --no-dev --package reflex`,
which lists `reflex` and every workspace package it needs (`reflex-base`,
`reflex-components-*`, ...) as editable paths in the checkout, so the
development versions reflex pins never come from PyPI; the other dependencies
are the locked ones, and the exported list is kept in the venv as
`reflex-bench-requirements.txt`. A checkout without a lock (older than uv) is
installed directly, editable.

The subject records its interpreter, `reflex_version`, `python_version` and
`extra.granian`, all read by running the subject's interpreter on package
metadata (the harness never imports reflex), plus `commit` and `dirty` for git
and path subjects. Benchmarks get the subject's interpreter directory first on
`PATH` in `ctx.env`, so commands reflex starts by name (reflex 0.8 starts
`granian` in production mode) come from the subject's venv.
`subjects list` and `subjects prune` manage the cached venvs.

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
not part of the name or the series key, `suite_params={"smoke": {"sessions":
[10]}}` for the values a parameter takes when that suite is selected (a quick
subset of the grid; `--param` still wins), and `setup_timeout` (600 s) for
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
`NO_COLOR`, `PYTHONUNBUFFERED`, `PYTHONHASHSEED=0`, granian, the subject's
interpreter directory first on `PATH`), `rng` (seeded), `log`, `arm` and
`dims`: `setup` may name how the values are measured there, e.g.
`ctx.dims["memory_method"] = "cgroup"`, and the scheduler copies it into the
entry's `dims`, which are part of the series key, so differently measured
values never pair up in a comparison.

All hooks of an instance run on one worker thread, so thread-bound resources
(such as a sync Playwright browser) work across hooks. A hook that misses its
deadline ends the instance with status `timeout`; the stuck thread is abandoned
and the remaining teardown hooks run on a fresh one (as they do after Ctrl-C),
so `conclude` should kill whatever `sample` started. A hook still running a few
seconds after teardown keeps the work directory and skips the benchmark's
remaining parameter sets. `reflex_bench.registry.Instance` exposes the hooks as
zero-argument methods and `reflex_bench.scheduler.make_context` builds the same
context as the scheduler, for callers other than the scheduler.

**Keep heavy processes per sample.** During [`ab`](#ab-runs) both arms'
sessions are open at the same time, `setup` to `cleanup`. A benchmark that
keeps a heavy process (a server) alive between samples runs two of them at
once, which distorts both arms. Start per-sample processes in `prepare` or
`sample` and stop them in `conclude`. This is not enforced.

## Driving reflex

Benchmarks start the reflex under test as a user does, `<python> -m reflex ...`
with the subject's interpreter, through `reflex_bench.drivers.app_process`:

```python
from reflex_bench.collectors.cgroup import CgroupScope
from reflex_bench.drivers.app_process import AppProcess, cache_env, run_cli

env = {**ctx.env, **cache_env(reflex_dir=ctx.cache_dir / "reflex")}
scope = CgroupScope() if CgroupScope.available() is None else None
result = run_cli(
    ctx.subject.python,
    ["compile"],
    cwd=app,
    env=env,
    timeout=600,
    scope=scope,
    phases=True,
    sample_memory=scope is None,
).check()  # wall_s, cpu_s, peak_mem_bytes, timing, attribution()

self.app = AppProcess(
    ctx.subject.python,
    app,
    mode="prod",
    reflex_version=ctx.subject.reflex_version,
    env=env,
)
readiness = self.app.start()  # process-ready: ready lines + every port accepts TCP
self.app.wait_http_ready()  # GET / (or /ping without a frontend) answers 200
# conclude(): self.app.stop() kills the whole process tree
```

The driver picks free ports, expects the ready lines of the subject's version
and mode (0.8.23 prod runs sirv and the backend on two ports, 0.9 prod one
port) and never trusts a line without a TCP probe. It runs with the `env` it
is given: pass `ctx.env`, or `reflex_bench.context.subject_env(python)` outside
a benchmark, so the subject's commands come first on `PATH`. Each command runs in its own session; `stop()` and the end of
`run_cli` kill the whole tree, children that started their own session
included. Peak memory and CPU come from a transient cgroup v2 scope when
`systemd-run` works (user manager, or sudo on CI), else from PSS sampling
(`memory_method: pss_sampling`, never compared with cgroup peaks);
`reflex-bench doctor` shows which. `selftest.app.compile` and
`selftest.app.dev_ready` exercise all of it against a blank app.

## Event benchmarks

`reflex_bench.suites.events` measures how many events the playground
(`examples/playground`) answers and how fast. Each benchmark instance starts it
once as a production backend (`reflex run --env prod --backend-only`, one
granian worker), and each sample drives it for a few seconds with
`reflex_bench.drivers.events`, a socket.io load generator that speaks reflex's
event websocket over `websockets` (no python-socketio). Sessions are browser
tabs: each connects with its own token, hydrates like a page load, then sends
`BenchState.set_seq*` events whose delta echoes a sequence number.

CI minutes are scarce, so `smoke` and `daily` run two points, about 2 minutes
per reflex with the default policy: `events.simple.capacity[manager=memory,sessions=10]`
and `events.simple.latency[manager=memory,sessions=10,rate=500]`. The other
shapes, managers and session counts, the knee and `at_1hz` run with
`--suite all` or by name.

| Benchmark | Suites | Parameters | Load | Metrics |
| --- | --- | --- | --- | --- |
| `events.<shape>.capacity` | `smoke`, `daily` (simple, `manager=memory`, `sessions=10`) | `manager`, `sessions` 1, 10, 50, 200 | closed loop, 3 s after 1 s | `throughput`, `service_p50`, `cpu_per_event` |
| `events.<shape>.latency` | `smoke`, `daily` (simple, `manager=memory`, `sessions=10`, `rate=500`) | `manager`, `sessions`, `rate` | open loop, 5 s after 1 s | `response_p50`, `p90`, `p99`, `max`, `throughput`, `unanswered`, `cpu_per_event` |
| `events.simple.knee` | (`all`) | `manager`, `sessions` | open loop at 10 % to 110 % of the capacity, 4 s after 1 s each | `knee_rate`, `low_load_p99` |
| `events.sessions.at_1hz` | (`all`) | `manager`, `sessions` 50, 200, 1000 | open loop, 1 ev/s per session, 10 s after 3 s | `response_p50`, `response_p99`, `unanswered`, `cpu_per_event` |
| `selftest.events.calibrate` | `selftest` | | the generator against an echo server: closed loop, then open loop at 3000 ev/s | `closed_ceiling`, `open_lag_p99` |

- **Shapes**: `simple` (`set_seq`), `complex` (three vars behind a chain of
  three computed vars), `cross` (`get_state` of another state), `background` (a
  background task). Background tasks may finish in any order, so for
  `background` an answer that overtakes an earlier event counts as
  `out_of_order` without making that event unanswered. SharedState fan-out and
  contention come with the playground's SharedState surface.
- **`manager`**: `memory` and `disk`, plus `redis` when `REFLEX_REDIS_URL` is set
  in the harness's environment when the suite is imported. The URL reaches only
  the redis instances: reflex uses redis whenever a URL is configured.
- **`rate`**: `auto` offers half the capacity that a 2 s closed-loop probe
  measures once per instance, so each arm of an `ab` run is loaded to the same
  share of its own capacity; `--param rate=N` offers `N` events per second to
  both, which compares the same absolute load. `smoke` and `daily` offer 500,
  the same load from one day to the next.
- **One backend per instance**: it starts in `setup`, which also warms it with
  the probe, and stops in `cleanup`, so its samples share one warm server; in
  an `ab` run both arms' backends are up, one idle while the other is measured.
- **Open and closed loop**: the open loop sends on a fixed schedule whatever
  the server does and times each answer from the *planned* send time, so a
  stall counts in every event it delays (no coordinated omission); events
  without an answer count as `unanswered`, never dropped. The closed loop sends
  the next event when the previous one is answered: it measures capacity and
  service time (answer minus actual send), never user latency.
- **Rates count the window only**: `throughput` (`answered_rate`) is the
  answers that arrived within the measured window divided by its length, the
  same as `answered_per_second` summed. The drain after the window only decides
  which events are `unanswered`; the answers it collects still count in the
  response percentiles.
- **Per run, not pooled**: every sample's percentiles come from that run's
  events; `response_p99` of a run with fewer than 10 000 answered events is kept
  with `p99_underpowered` in its extra data. Each sample's extra data also holds
  a 120-bucket log histogram (10 μs to 100 s) for pooled percentiles on display.
- **CPU per event** is the server tree's CPU time in the measured window divided
  by the answered events: from its cgroup scope (`cpu_method: cgroup`) or,
  without one, summed over its processes with psutil (`cpu_method: psutil`),
  including the children they reaped, so a worker that exits in the window
  still counts. A CPU time that goes back fails the sample.
- **Pinning**: on Linux with four CPUs or more, the server runs on the lower
  half of the physical cores (CPU 0 excluded) and the generator on the upper
  half, so no core is shared between them through SMT (the kernel's
  `thread_siblings_list`; without it every CPU counts as a core), with up to 4
  generator processes (1 up to 10 sessions); `pinning` in the extra data
  records the split.
- **Self-check**: a load fails it when a generator process used more than
  75 % of a core, when the p99 of the send lag (actual minus planned send
  time) exceeds the larger of 1 ms and 10 % of the median response, or when
  less than 98 % of the offered events went out in the window. The rules judge
  the generator alone: a lag tail inflates the response tail by as much,
  whatever caused it, so the sample fails with `generator saturated` at once
  and is never taken again. `selftest.events.calibrate` fails the same way
  when the generator cannot offer 3000 ev/s, three times the highest fixed rate
  of the suite, against an echo server.

Not parameters yet: injected redis latency, uvicorn instead of granian, and
more than one backend worker.

## Memory benchmarks

`reflex_bench.suites.memory` answers how much memory the playground takes,
whether it grows, and whether it fits a 512 MiB box. Samples are untimed:
every metric is bytes (lower is better) except `passed`. Each sample starts a
fresh backend (`reflex run --env prod --backend-only`, one granian worker), as
the event benchmarks do.

| Benchmark | Suites | Parameters | One sample | Metrics |
| --- | --- | --- | --- | --- |
| `memory.compile.peak` | `daily` | `command` compile, export | `reflex compile` or `reflex export --env prod` of the compiled playground | `peak_mem` |
| `memory.idle` | `smoke` (memory), `daily` | `manager` | 5 s after `/ping` answers, the median of three PSS reads a second apart | `pss`, `pss_anon`, `pss_file` |
| `memory.idle.allocator` | (`all`) | `allocator` mimalloc, arena2 | the same with `PYTHONMALLOC=mimalloc` or `MALLOC_ARENA_MAX=2` | the same |
| `memory.per_session` | `daily` (`max_sessions=500`) | `manager`, `max_sessions` (1000) | hold 0, 50, 100, 250, 500 and 1000 idle sessions, fit PSS per session; disconnect; wait for the states to expire | `bytes_per_session`, `bytes_per_session_ci_hi`, `residual_after_disconnect`, `residual_after_expiry` |
| `memory.leak` | `daily` (`events=50000`) | `manager`, `events` (100000) | a closed loop of 10 sessions while the tree's anonymous PSS is sampled | `passed`, `bytes_per_event_ci_hi` |
| `memory.boot_512mb` | `daily` (memory) | `manager` | compile, then boot and serve, under `MemoryMax=512M` with swap off | `passed`, `peak_compile`, `peak_boot`, `peak_serve` |
| `memory.boot.min_limit` | (`all`) | `manager` memory | bisects `MemoryMax` from 64 to 1024 MiB in 32 MiB steps over boot and serve | `min_limit` |

- **Methods**: peaks come from a cgroup v2 scope's `memory.peak` where the host
  can start one (user systemd, or `sudo systemd-run` on CI), else from PSS
  sampled every 50 ms; steady-state values are the summed PSS of the server's
  process tree on every host, with the scope's `memory.current`, `anon` and
  `file` in the extra data when a scope holds the running server (the compile
  peak reads its scope after the command exited, so it records only whether
  the peak was reset). `memory_method` in the dims
  (`cgroup` or `pss_sampling`) names the collector of the values, so cgroup and
  PSS numbers never share a series. The limit benchmarks need a scope and fail
  with `cgroup scopes are unavailable: <reason>` without one: nothing else can
  enforce a limit. `reflex-bench doctor` shows what the host has.
- **What PSS shows**: the memory the tree holds from the kernel, shared pages
  split between the processes. CPython and glibc keep freed memory for reuse
  and rarely hand it back, so a number that does not drop means the process did
  not shrink, not that something leaks. File-backed pages are also split with
  processes outside the tree that map the same files (the harness's own
  interpreter), so `pss_file` moves by a few MB between otherwise identical
  samples; `pss_anon` is the steadier trend.
- **Per session**: the sessions connect and hydrate like page loads, then stay
  idle, held by `reflex_bench.drivers.events.hold_sessions` in a separate
  process. The server runs with `REFLEX_REDIS_TOKEN_EXPIRATION=<expiry_s>`
  (hidden; 0, the default, sizes it from the sweep: its settling and reading
  time, 2 s per hold and a 5 s margin, 23 s for 500 sessions), longer than the
  sweep: no state manager frees a state when its session disconnects, reflex
  0.9's memory and disk managers and 0.8's disk manager free it after the
  expiration, and 0.8's memory manager never does. A sweep that outlasts the
  expiration fails the sample; a slow host can raise `expiry_s`. The residuals
  are PSS over the idle baseline. `baseline_bytes_per_session` in the extra
  data is the same sweep against the in-harness echo server: the floor of a
  Python `websockets` server, not of python-socketio (the harness does not
  depend on python-socketio); it is measured once per instance, while the
  first sample's states expire. The sweep's steps below `max_sessions` are 50,
  100, 250 and 500, so the slope's t interval has at least three degrees of
  freedom. The tree's PSS is flat within 0.2 MiB from the moment a hold is
  ready (against steps of 8 to 47 MiB), so a step settles for 1 s and is read
  three times 0.5 s apart: about 2.5 s each, and a sample about 40 s.
- **Leak**: a 5 s closed-loop probe sizes the warmup (`warmup_events`, hidden,
  5000) and the window (`events`, with 10 % of room); the tree is sampled every
  hundredth of the window, between 0.1 s and 1 s apart. The x axis is the events
  answered since the window started (`answered_per_second` of the load), the y
  axis the anonymous PSS: file-backed pages do not leak. The sample fails with
  `LeakDetected` when the upper end of the slope's 95 % interval exceeds
  `tolerance_bytes_per_event` (hidden, 100 B, that is 100 MB per million
  events) *and* each half of the window grows on its own (the lower end of its
  slope's interval is above zero): heap warm-up flattens out and one allocator
  step lifts one half only, a leak grows through both. One 1 MiB arena step in
  50 000 events is about 30 B per event. An unanswered event or a failed
  session fails the sample, since the event count would be wrong. `passed` is
  the gate; the slope itself and the growth over the window are in the extra
  data (`slope_bytes_per_event`, `growth_bytes`), since near zero they move by
  hundreds of percent between identical runs. `timeline` in the extra data
  holds up to 500 `[events, anonymous PSS, USS of the python processes]`
  points.
- **512 MiB**: the compile runs in one scope, the server boots and serves 5
  closed-loop sessions for 5 s in another, each with `MemoryMax=<limit_mb>M`
  (hidden, 512) and `MemorySwapMax=0`, and each scope is read before its tree
  stops. A phase that fails, or any `oom` or `oom_kill` in `memory.events`,
  fails the sample with `MemoryLimitExceeded` naming the phase, the counters,
  the peak and the log tail. The peak is reset between boot and serve where
  the kernel can (Linux 6.12 and later; `peak_reset` in the extra data says
  so), else the serve peak includes the boot. The published 512 MiB number
  comes from an
  amd64 reference profile (Fly's `shared-cpu` machines are amd64); arm64 runs
  are a trend.
- **Allocators**: `--param allocator=mimalloc|arena2` also works on `memory.idle`,
  `memory.per_session` and `memory.leak`, and puts the allocator in the dims.
  mimalloc needs the subject's Python to be 3.13 or later.

Not measured yet: a leak per session (connect/disconnect churn) or per page
load, redis's `used_memory` per session, and peaks per phase within one command
(they need `memory.peak` resets, Linux 6.12).

**Finding a leak** (manual; tracemalloc slows the server and inflates its
memory, so it never runs in a measured sample). Add a temporary handler to the
app's state:

```python
@rx.event
def heap_snapshot(self, seq: int):
    import time, tracemalloc

    tracemalloc.take_snapshot().dump(f"/tmp/heap-{time.time_ns()}.bin")
    self.last_seq = seq
```

start the backend with tracemalloc on in every process
(`PYTHONTRACEMALLOC=25 GRANIAN_WORKERS=1 REFLEX_STATE_MANAGER_MODE=memory
python -m reflex run --env prod --backend-only --backend-port 8000`), and drive
it with the generator: a snapshot, a load, another snapshot.

```python
from reflex_bench.drivers.events import EventShape, LoadPlan, run_load, seq_payload

state = "reflex___state____state.playground___state____bench_state"


def load(handler: str, sessions: int, duration_s: float) -> None:
    shape = EventShape(f"{state}.{handler}", seq_payload, state, "last_seq_rx_state_")
    run_load(
        LoadPlan(
            backend_url="http://localhost:8000",
            reflex_version=None,
            shape=shape,
            sessions=sessions,
            mode="closed",
            rate=None,
            warmup_s=0,
            duration_s=duration_s,
        )
    )


if __name__ == "__main__":
    load("heap_snapshot", 1, 0.001)
    load("set_seq", 10, 60)
    load("heap_snapshot", 1, 0.001)
```

Then compare the two snapshots by line:
`first, second = map(tracemalloc.Snapshot.load, sorted(glob.glob("/tmp/heap-*.bin")))`
and print `second.compare_to(first, "lineno")[:20]`.

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

## A/B runs

`ab` answers "is my branch faster?" on one machine. Timing one subject fully
and then the other lets machine drift (thermal state, background load, caches)
bias the result, so `ab` interleaves them, as asv `continuous` does:

```console
$ uv run reflex-bench ab --base git:main --head workspace --suite pr
$ uv run reflex-bench ab --head workspace --aa --suite pr
```

1. Both subjects are built first (arm A is `--base`, arm B is `--head`).
2. For each benchmark instance, both arms' sessions are opened (`setup` of A,
   then B) and fill one result entry.
3. Warmups alternate A, B (`--warmup`, default per benchmark), then each of the
   `--rounds` timed rounds (default 10, a fixed count per arm) samples both
   arms: AB, BA, AB, ... with `--order abba` (the default), or a seeded coin
   flip per round with `--order random`.
4. A failure in either arm ends the instance; `failed_arms` records which.
5. The arms are summarized and compared, B against A, with the statistics of
   `compare`; a failure in B alone is a regression. The result stores both
   subjects (`subjects.A`, `subjects.B`) and is autosaved like a `run`.

`--aa` measures `--head` in both arms (A/A): a sound setup reports no change or
inconclusive for almost every metric, and the spread shows the noise floor. It
records `invocation.kind = "aa"`. `ab` takes `run`'s parameter, timeout, seed,
statistics, `--fail-on`, save, `--json` and `--ndjson` options.

The workspace runs on the harness's Python and other subjects on `--python`,
which defaults to the harness's major.minor, so both arms match by default.
`ab` warns when the two arms run different Python versions (for example
`--python 3.12` against `workspace` on 3.14): match them with `--python`, or
use `path:<checkout>` for the current checkout.

When an arm's values of a metric trend with their position in the interleaved
sequence, significantly (Spearman's rho with p < 0.01: exact up to 10 samples,
a normal approximation above) and strongly (|rho| >= 0.5), the metric warns
`drift: <metric> trends with time in arm <A|B> (rho=…, p=…)`: the machine or
the benchmark's state probably drifted during the run. An arm without any trend
warns by chance at most 1 % of the time; 6 samples are the fewest that can
reach p < 0.01.

## Results

One JSON document per invocation, schema `reflex-bench/1` (see
`reflex_bench/schema.py`): `schema`, `tool`, `invocation` (argv, times, mode,
kind, CI run, seed), `subjects` (arm `A`, and `B` for `ab`), `machine` (with
`profile_id`), optional `fixture`, `policy` and `benchmarks`. Each benchmark
entry keeps its status, error and traceback tail (and `failed_arms`, the arms
whose hooks failed), every raw sample per arm (warmups included and marked in
`sample_meta`), per-sample extra data, and the derived summaries, warnings and
comparisons. Documents are validated on load and before every write.

Local storage lives in `.reflex-bench/` at the root of the git checkout (or the
working directory), or in `$REFLEX_BENCH_HOME`:

```
results/<profile_id>/<NNNN>_<short sha>[_dirty]_<UTC timestamp>.json
results/<profile_id>/.claims/<NNNN>
baselines/<profile_id>/<name>.json
cache/<commit>[-dirty]/<benchmark id>/<params hash>/
venvs/<key>/                subject virtualenvs
src/<commit>/               git worktrees of git: subjects
locks/                      locks of venv and worktree builds
```

The cache is keyed by the subject's commit (its spec when the commit is
unknown).

The machine profile id is `<os>-<arch>-<cpu model>-py<major.minor>`, for example
`linux-x86_64-ryzen-9-7950x-py3.12`; `REFLEX_BENCH_PROFILE` overrides it (other
characters than letters, digits, `.`, `_` and `-` become `-`). Results from
different profiles are never compared.
