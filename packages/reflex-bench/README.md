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
$ uv run reflex-bench budgets check result.json
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
| `budgets check FILE [--budgets BUDGETS]` | Checks a result against the metric maxima of `budgets.json` ([Size budgets](#size-budgets)). |
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
`sample` and stop them in `conclude`. This is not enforced. Two kinds of
benchmarks keep one server per instance on purpose, and say why in their
docstrings: `browser.prod.pageload` (a prod start includes a full frontend
build, and an idle second server does not touch page load) and the `hmr.*`
benchmarks (a dev start plus hydration before every edit would multiply their
run time by about ten, and the other arm's server only idles while this one
recompiles).

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
`reflex-bench doctor` shows which. With `phases=True`, `attribution()` splits
the command's wall and CPU time between three classes of processes sampled
from its tree: `install` (`bun`/`npm`/`pnpm`/`yarn` `install`/`add` and what
they start), `frontend` (`node`, `vite`, `react-router`, `esbuild` and what
they start) and `python`, the interpreter and everything else. A tool's wall
is the time it was alive; python's is the total minus the time any tool was
alive, when the interpreter only waits. `cpu` per class is checked against
the measured total (`mismatch` beyond 10 %), `idle` is wall time not spent on
CPU, and `python_breakdown` keeps the `[timing]` phases of the compile.
`selftest.app.compile` and `selftest.app.dev_ready` exercise all of it against
a blank app.
`run_cli(..., prefix=("-c", "import reflex"))` runs other interpreter
arguments than `-m reflex` through the same process tree code.

## Fixtures

A fixture is the app a benchmark drives, described by a `FixtureDoc` (`name`,
`content_hash`, `params`). A benchmark sets `ctx.fixture` in `setup_cache` or
`setup`, and its entry records the name in `dims` (`{"fixture": "playground"}`,
part of the pairing and series keys) and the hash in `fixture_hash` (part of
the series key only): an edited fixture pairs with its old self and `compare`
reports the pair as not comparable, `fixture content hash differs`, unless
`--force`. Hooks record anything else that separates series in `ctx.dims`.
One invocation drives several fixtures, so the document-level `fixture` stays
`null`.

- **The playground**, `examples/playground`: a committed app whose hash is the
  line in its `.content-hash` (see its README for the element ids and hot reload
  targets benchmarks rely on). `materialize_playground(dest)` copies it without
  build output.
- **Generated apps**, `reflex_bench.fixtures.generate`: `GenParams(pages,
  components_per_page, state_vars, substate_depth, computed_vars, seed)` gives a
  deterministic app of any size, hashed from the generator's source and the
  parameters. Its hot reload targets follow the playground's pragma form and
  are listed in `bench-manifest.json`. `uv run python -m
  reflex_bench.fixtures.generate --pages 10 DEST` writes one to look at.

`ensure_fixture(ctx.cache_dir, describe, make)` keeps the app in
`cache_dir/app` with a `fixture.json` stamp, and rebuilds it when the stamp no
longer matches: `setup_cache` directories are keyed by subject and parameters,
not by the app. `bump_marker(path, target, n)` sets a hot reload target's
string to `m-<n>-<target>`; the benchmark restores the module in `conclude`, so
the cached app stays the fixture its stamp describes.

The `lifecycle.*` benchmarks (`reflex_bench/suites/lifecycle.py`) time `init`,
`compile`, `export`, `run` until HTTP-ready and `import reflex as rx; rx.App;
rx.State` (the import alone is lazy), each in a cache state its id names
(`cold`, `warm`, `incremental`); the module docstring lists which caches each
one starts from. No sample downloads anything: a subject downloads bun once,
into its shared `REFLEX_DIR` (`ctx.subject_cache_dir/reflex`), and installs the
playground's packages once, into its shared bun cache
(`ctx.subject_cache_dir/bun-cache`); a cold state is a fresh directory that
these primed copies fill (`init.cold` gets a copy of bun, `compile.cold` a fresh
app copy with the primed lockfile that links its packages from the cache), so a
sample measures reflex and bun, not the network. Each `time` benchmark chooses its collector once, in
`setup`, and records it in `dims` (`collector: cgroup | fallback`), so cgroup
peaks and PSS peaks never share a series.

## Fixture apps

The browser and hot reload benchmarks drive `examples/playground` (see its
README for the element ids and `# bench:hmr-target` pragmas they rely on). The
harness reads it from the checkout it runs in, never from the subject's
environment, so `reflex-bench` must run from a reflex checkout.
`reflex_bench.fixtures.prime(ctx)` copies it into the instance's cache directory
(`<cache>/app/<arm>`: in an A/A run both arms share a cache directory, and two
servers must not run in one app), without build output, and compiles it once
(bun and the frontend packages), so the benchmarks' own starts are warm. The
staged copy is what the hot reload benchmarks edit; the checkout never changes.
Every sample records the playground's `.content-hash` in
`extra["fixture_hash"]`. `reflex_bench.fixtures.FIXTURES` maps the `app`
parameter of the hot reload benchmarks to a staging function; `playground` is
the only one so far.

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
the event benchmarks do; `memory.dev.idle` starts the dev server instead.

| Benchmark | Suites | Parameters | One sample | Metrics |
| --- | --- | --- | --- | --- |
| `memory.compile.peak` | `daily` | `command` compile, export | `reflex compile` or `reflex export --env prod` of the compiled playground | `peak_mem` |
| `memory.idle` | `smoke` (memory), `daily` | `manager` | 5 s after `/ping` answers, the median of three PSS reads a second apart | `pss`, `pss_anon`, `pss_file` |
| `memory.idle.allocator` | (`all`) | `allocator` mimalloc, arena2 | the same with `PYTHONMALLOC=mimalloc` or `MALLOC_ARENA_MAX=2` | the same |
| `memory.dev.idle` | `daily` | `manager` memory | the same for `reflex run --env dev`, backend and vite dev server, 10 s after the page answers HTTP (no browser, so vite has transformed only what that request needed); the USS of the node, bun and esbuild processes is split from the python ones in the extra data (`backend_uss_bytes`, `frontend_uss_bytes`) | the same |
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
uv run reflex run --env prod --backend-only --backend-port 8000`), and drive
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

## Wire sizes

`reflex_bench.suites.wire` counts the bytes that cross the event websocket: what
a slow link pays for, which no timing or CPU metric shows. One session connects
to a fresh production backend per sample (`reflex run --env prod
--backend-only`, one granian worker, the memory state manager) and sums the
payload bytes of every frame it sends and receives (a text frame's UTF-8
length; the HTTP handshake is not a frame). Sizes are deterministic for a given
app and reflex version, so every metric is exact and a sample is one run.

| Benchmark | Suites | Parameters | One sample | Metrics |
| --- | --- | --- | --- | --- |
| `wire.hydrate` | `pr`, `smoke`, `daily` | | connect and hydrate the playground's index route, until the delta that sets `is_hydrated` | `hydrate_sent_bytes`, `hydrate_received_bytes`, `hydrate_frames` (received) |
| `wire.event` | `pr`, `smoke` (simple), `daily` | `shape` simple, complex, cross, background | after hydration, one `BenchState.set_seq*` event: the request frame, and every frame received until the delta echoing its sequence number | `request_bytes`, `response_bytes`, `response_frames` |
| `wire.navigate` | `pr`, `smoke` (item), `daily` | `route` counter (`/counter`), item (`/item/42`, the dynamic `/item/[item_id]` page) | after hydration of `/`, a client-side navigation: the `on_load_internal` frame the frontend's router effect sends from the new route, and every frame received until the delta that sets `is_hydrated` again | `request_bytes`, `response_bytes`, `response_frames` |
| `wire.delta` | `daily` | `change` set_scalar, append_item, set_one_item, set_dict_key, update_row_field | the same for one small change to a large collection of the generated `wire_delta` app | `response_bytes` |

- **Replies span frames**: `response_bytes` sums every frame from the request
  until the echo, so 0.8.23's empty update before a background task's delta
  counts, as does any delta of another state. The extra data keeps the echo
  frame (`reply`), the largest frame, and `delta_bytes`, the bytes of each
  substate's part of the deltas re-serialized compactly.
- **Keepalives do not count**: an engine.io ping and its pong are timing, not
  payload, so a slow run moves the same bytes as a fast one.
- **`wire.navigate`** sends what the frontend sends on a route change: one
  `on_load_internal` with the new route's `router_data` (`update_vars_internal`
  goes first only when the browser holds client storage vars, which the
  playground has none of). The reply carries the root state's `router` and,
  on the dynamic route, the route argument.
- **`wire.delta`** does not use the playground: its `setup_cache` writes a
  small app whose state holds 1000 ints in a list, 1000 keys in a dict and 200
  dict rows, and compiles it. Every handler also sets `last_seq` (the echo), so
  the deltas differ only by the collection they carry; `set_scalar` is the
  control. A whole collection resent for a one-item change shows as
  `response_bytes` far above the control's.
- **Dims**: `fixture` names the app (`playground` or `wire_delta`); for
  `wire.delta`, the entry's `fixture_hash` is the generated source's content
  hash, so `compare` rejects a pair across a change to the generator.

`AppProcess.t0` is the `time.perf_counter()` taken just before the spawn, the
origin of every readiness time, and `AppProcess.log_lines()` returns the output
with the time each line was read (seconds since `t0`), so other clocks and log
lines can be put on one timeline.

## Driving a browser

`reflex_bench.drivers.browser` drives headless Chromium through Playwright's
sync API. Install the browser once:

```console
$ uv run playwright install --only-shell chromium
```

Headless runs launch the headless shell, so the full Chromium is not needed
(`--only-shell` exists from Playwright 1.49). On a bare CI runner add
`--with-deps` for the system libraries, and cache `~/.cache/ms-playwright`
keyed on the runner's architecture. `reflex-bench doctor` reports whether a
chromium is installed.

```python
from reflex_bench.drivers.browser import Browser

self.browser = Browser(cpu_throttle=1)  # setup(): one browser per instance
self.browser.start()  # the calling thread owns it
result = self.browser.interactive(self.app, "/")  # tier 3, also set in app.readiness
tab = result.tab  # a page in a fresh context (cold cache); tab.page is Playwright's
tab.watch("edit", "text", "#bench-marker-leaf", marker)
mark = tab.wait_mark("edit", timeout=90)  # {"perf": ..., "epoch": ...}
# conclude(): self.browser.close_tab(tab); cleanup(): self.browser.close()
```

Every page gets `drivers/bench_page.js` as an init script, which runs before
any page script in every document, reloaded ones included. The page emits the
"done" signal itself: `tab.watch(id, kind, selector, expected)` has it record a
*mark* the first time a condition holds (`present`, `text`, `changed`,
`style:<property>` or `naturalWidth`), checked on every DOM mutation and every
animation frame (a computed style or a loaded image is no mutation); a watch,
and its mark once recorded, survives a reload. `#bench-hydrated` is always watched: `interactive()` waits
for it (tier 3: the websocket connected and the first state update applied).
The script also collects paint, largest contentful paint, long task and long
animation frame entries (`tab.timings()`). `tab.set_alive()` tags the document
and `tab.alive()` reads the tag back: a full reload loses it. Uncaught page
errors fail a sample (`tab.raise_errors()`), console errors and warnings are
counted (`tab.drain_console()`, the last error's text in `tab.last_error`), and
websocket payload bytes and HTTP wire bytes (headers included, from the
DevTools `Network.loadingFinished` events) are summed per page.

**Clocks.** A mark carries `performance.now()` (since navigation start) and
`Date.now()`. `browser.anchor`, the tightest of three back-to-back reads of
`time.perf_counter()` and `time.time()` taken at start, maps page time onto
`perf_counter()`: `anchor.perf_at(epoch) - app.t0` puts a page event on the
app's timeline within 1 ms (`Date.now()`'s resolution) plus the anchor's
spread, the harness's own share (well under a microsecond), which is stored
with the samples.

**Threads.** The sync API refuses calls from any thread but the one that
started it (`greenlet.error: Cannot switch to a different thread`), and
teardown hooks run on a fresh thread after a timeout or Ctrl-C. `close()`
closes normally on the owner thread and kills from any other; `kill()` never
touches Playwright: it SIGKILLs the Playwright driver (the harness's child) and
the process group Chromium's root (the driver's child) leads with all its
helpers, both found at `start()`, so a hook still blocked in the page gets an
error at once. `close_tab()` from another thread kills the
browser too: after a timeout the instance is over. Browsers still open when the
harness exits are killed. A `Browser` belongs to one instance and arm; during
`ab` two of them coexist. Playwright is imported on `start()`, which keeps
`reflex-bench list` about 0.1 s faster.

## Browser benchmarks

| Id | Suites | What one sample measures |
| --- | --- | --- |
| `browser.dev.ready` | pr, daily | `reflex run` start to `process_ready` (tier 1), `http_ready` (tier 2) and `interactive_ready` (tier 3), seconds since the spawn; also `nav_to_interactive` (in the page) and `fcp` |
| `browser.preview.ready` | daily (reflex 0.9.8+) | the same with `--env preview` |
| `browser.prod.ready` | daily | the same with `--env prod`, frontend build included |
| `browser.prod.pageload[cpu=1\|4]` | daily | loading `/` of one prod server in a fresh context (cold cache), CPU throttled 4 times with `cpu=4`, read as soon as the page is interactive: `fcp`, `lcp` (the same paint on the playground), `interactive`, `tbt` (long tasks' time beyond 50 ms before interactive), `ws_bytes`, `transfer_bytes` (wire bytes, headers included; both exact: the same page transfers the same bytes) |

The `ready` samples store the gaps between the tiers in `extra["gaps"]`. Page
load metrics are noisy: read the median and its confidence interval over at
least 6 runs (outliers are counted, not dropped).

## Hot reload benchmarks

Each `hmr.*` instance starts one app (`reflex run --loglevel debug`) and one
page, then per sample rewrites the staged app and waits until the page shows
the change. The edit's content is built in `prepare`; `sample` writes it to a
sibling temporary file and moves it over the target, taking `t0` just before
that one `os.replace`, and returns as soon as the page's mark is there.
`latency` is the page's mark minus `t0`, on the wall clock of both. Every edit
writes a unique value, so a stale page never satisfies a watch. `conclude`
waits until the page has been quiet for 0.5 s (no pending watch, no DOM
change), restores the file and waits until the page shows the original and is
quiet again, which is also the wait between edits. Every hook's waits share
one 90 s deadline. `warmup` is 3 edits.

| Id | Edit | Done when the page shows |
| --- | --- | --- |
| `hmr.render.leaf` | the `leaf` pragma literal (index page only) | the new text in `#bench-marker-leaf` |
| `hmr.render.root` | the `root` pragma literal (every page) | the new text in `#bench-marker-root` |
| `hmr.handler` | the `handler` pragma literal, set by an event handler | the new value in `#bench-handler-value`; the harness clicks `#bench-handler` every 250 ms (`extra["clicks"]`) |
| `hmr.css` | the `.bench-hooks` font size in `assets/playground.css` | the computed font size |
| `hmr.asset` | `assets/mark.svg` gets a `width` and `height` | `#bench-mark`'s `naturalWidth` (HTTP cache off); the harness refreshes the page every 250 ms (`extra["reloads"]`) |
| `hmr.reconnect` | none: SIGKILL of granian's worker, then SIGHUP to its supervisor, since granian's dev reloader never respawns a worker that died on its own | `#count` changes on `/counter`; the harness clicks `#increment` every 250 ms |
| `hmr.watcher` | the `leaf` literal | `latency` is granian's `Changes detected` line (its `reload_tick` is 100 ms) |

Every benchmark but `hmr.watcher` has a `.preview` twin for `--env preview`
(reflex 0.9.8+). Preview serves a static build that a hot reload rebuilds and
that shows after a refresh, so preview twins whose change needs a new page
reload it (waiting for its load event) every 250 ms until it shows
(`extra["reloads"]`).

`full_reloads` records whether the sample's page reloaded to show the change
(the mark carries the document's `tab.alive()` tag; a reloaded document lost
it). For the render, handler and reconnect benchmarks a reload is no hot
update: `conclude` fails the sample with `FullReloadError`, also when the page
reloads right after showing the hot update, so `latency` only holds hot
updates. For `hmr.css` a reload may be how the change shows: `latency` is the
time until it shows. A change the page never shows by itself (no hot update,
no reload, within the deadline) fails the sample: the harness does not refresh
a dev page for it. The error then says when granian saw the change, when the
reload's last `[timing]` line came and whether the page reloaded, so it tells
which side dropped the change. A stylesheet hot update that vite logged
(`[vite] ... hmr update`) 5 s ago without the page applying it fails the sample
at once (`DroppedUpdateError`, naming the value the page still shows) instead
of waiting the deadline out. `hmr.asset` refreshes the page itself in every
mode: vite has no module for a file of `public/`, so a change to one reaches
no page and a user refreshes for it; `latency` is the time until a refresh
shows the new file and `extra["reloads"]` counts the refreshes.
`extra["hops"]` places each sample's backend steps, in seconds
since the edit: `watcher_seen_s` (granian's line), `compile_done_s` (the
reload's last `[timing]` line) and `dom_updated_s` (the page's mark).

## Size budgets

`size.export[app=playground]` (suites `pr` and `daily`) measures what a
production build of `examples/playground` ships. Its `setup` copies the files
git tracks of the example into the instance's work directory (each arm of an
`ab` run gets its own copy; `--keep` keeps it) and runs `reflex export
--frontend-only --no-zip --env prod` there; bun stays cached in reflex's data
directory under the cache directory. `sample` then measures the files on disk.
One export gives every metric, and every metric is exact, so one sample is
taken:

| Metric | What |
| --- | --- |
| `initial_raw`, `initial_gzip`, `initial_brotli` | The JS and CSS the first page loads: the files the prerendered `index.html` references with `<link rel="modulepreload">`, `<link rel="stylesheet">` or `<script src>`. URLs of other hosts are not part of the build. |
| `total_raw`, `total_gzip`, `total_brotli` | Every file of `.web/build/client` except compression sidecars. |
| `chunks` | The `.js` files of `.web/build/client/assets`. |
| `web_dir` | The regular files under `.web` outside `node_modules` (build output, compiled pages, templates). |
| `node_modules` | The regular files under `.web/node_modules`. Symlinks are neither followed nor counted, here and in `web_dir`. |

The harness compresses each file on its own, gzip at level 9 (`mtime=0`) and
brotli at quality 11. Reflex 0.9 writes `.gz` sidecars next to the build's files
(`.br` and `.zst` too when configured) and 0.8.23 writes none, so sidecars are
never measured, only summed into the extra data's `sidecar_bytes`. Each sample's
extra data also holds the per-file breakdown `files`: `raw`, `gzip`, `brotli` and
`initial` for each file of the client build, keyed by its path with the content
hash of names in `assets/` replaced (`assets/chunk-5KNZJZUH-q9CrfzJj.js` becomes
`assets/chunk-5KNZJZUH-HASH.js`; `#2` marks a second name that differed only in
its hash), plus `initial_files` in page order, `html` (the page parsed),
`reflex_version`, `fixture_hash` (the playground's committed `.content-hash`,
the hash the result series are keyed on and that CI keeps current; an
uncommitted playground edit shows in the subject's `dirty` flag instead),
`bun_lock` (the hash of `.web/bun.lock`) and the `compressors`' versions. Apps
with a `frontend_path` are not supported.

Two samples of one export are identical, but two exports of one commit are not
quite: reflex bundles `.web/reflex.json`, with a random `project_hash` and the
export's time, into a shared chunk (`assets/link-HASH.js` at 0.9.12,
`assets/esm-HASH.js` at 0.8.23). That chunk's content hash changes, and with it
every chunk that imports it, the manifest and the HTML pages. Raw sizes stay the
same up to a byte or two (the number of digits of the project hash), compressed
sizes move by a few bytes and `web_dir` by a few dozen: two runs in separate
bench homes measured `total_gzip` 328,699 and 328,683 B, `total_brotli` 263,247
and 263,218 B, `web_dir` 2,142,835 and 2,142,814 B, with the same `total_raw`,
`chunks` and `node_modules`. So `assume="exact"` means deterministic up to about
150 B per export here: an A/A `ab` run shows differences of a few bytes, far
below the budgets' headroom and the 3 % threshold of exact comparisons, so the
metrics stay exact and no file is left out of the breakdown. Reflex pins its own
frontend packages, but their dependencies are resolved when the export installs
them (the playground commits no lockfile), so a new release of one can change
the sizes of the same commit; a different `bun_lock` tells such a change apart
from a change in the code. `node_modules` drifts this way over time (25 kB in
18 hours on one commit), so its budget can go red on a pull request that
changed nothing related; raising it in that pull request is the expected fix.

`packages/reflex-bench/budgets.json` caps metrics, as whole numbers in the
metric's unit:

```json
{
  "schema": "reflex-bench-budgets/1",
  "budgets": {
    "size.export[app=playground]": {"initial_gzip": 330000, "chunks": 16}
  }
}
```

`reflex-bench budgets check RESULT.json [--budgets FILE]` prints one row per
budget (value, budget, delta in the unit and in percent of the budget, verdict)
and exits with `2` when a value (the largest timed sample) exceeds its budget,
`1` when a budget cannot be checked (the benchmark is not in the result, did not
finish `ok` or lacks the metric), else `0`. A metric without a budget is
tracked, not gated. To raise a budget, edit `budgets.json` in the same pull
request, so the review shows the new value; the value column prints it ready to
paste. The budgets come from a measurement plus about 5 % headroom (20 % for
`node_modules`, which moves with bun and the frontend packages' releases).

The `size-budgets` workflow runs `reflex-bench run 'size.*'` and `reflex-bench
budgets check` on every pull request that touches reflex, the packages or the
playground, on a standard GitHub runner, and uploads the result.

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
and benchmark version (a hash of the source of the benchmark class and its
bases). `compare --force` overrides that. For each metric:

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
whose hooks failed), its `dims` and `fixture_hash`, every raw sample per arm (warmups included and marked in
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
