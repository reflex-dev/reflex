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
`NO_COLOR`, `PYTHONUNBUFFERED`, `PYTHONHASHSEED=0`, granian, the subject's
interpreter directory first on `PATH`), `rng` (seeded), `log` and `arm`.

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
`reflex-bench doctor` shows which. `selftest.app.compile` and
`selftest.app.dev_ready` exercise all of it against a blank app.

`AppProcess.t0` is the `time.perf_counter()` taken just before the spawn, the
origin of every readiness time, and `AppProcess.log_lines()` returns the output
with the time each line was read (seconds since `t0`), so other clocks and log
lines can be put on one timeline.

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
| `hmr.asset` | `assets/logo.svg` gets a `width` and `height` | the logo's `naturalWidth` (HTTP cache off) |
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
updates. For `hmr.css` and `hmr.asset` a reload may be how the change shows:
`latency` is the time until it shows. A change the page never shows by itself
(no hot update, no reload, within the deadline) fails the sample: the harness
does not refresh a dev page for it. The error then says when granian saw the
change, when the reload's last `[timing]` line came and whether the page
reloaded, so it tells which side dropped the change. `extra["hops"]` places each sample's backend steps, in seconds
since the edit: `watcher_seen_s` (granian's line), `compile_done_s` (the
reload's last `[timing]` line) and `dom_updated_s` (the page's mark).

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
