# verify_pm1 — independent verification of PM-1 (process_model ISSUE-1, #7079 prod fork preload)

Claim under test: "Prod fork preload (#7079) silently kills import-time threads in every worker and shares
module-level random values / `random.Random()` sequences across workers. `reflex run --env prod --backend-only` on
Python 3.12 and any prod run on Python 3.14 regress vs 0.10.0; full-stack prod on 3.12 already behaved this way on
0.10.0. Severity medium. Documented trade-off (`REFLEX_BACKEND_START_METHOD=spawn`) but silent; PRNG / module-constant
sharing undocumented."

**Verdict: RECLASSIFIED — every factual part of the claim reproduces exactly as written (regression scope included);
severity lowered medium → low (documented, industry-standard preload semantics with a verified full workaround). The one
thing I would still ask for is release-notes/diagnostics, not a code change (details at the end).**

Venvs (all PyPI, read-only, Python 3.12.3): `$SB/envs/new` = reflex 0.10.1a1, `$SB/envs/prev` = 0.10.0 (granian 2.8.5
in both); `$SB/envs/process_model-py314-{new,prev}` = the same on Python 3.14.6 (built by the process_model agent, reused);
`$SB/envs/verify_pm1-otel` = `reflex[db]==0.10.1a1 reflex-otel==0.2.0 opentelemetry-sdk==1.45.1 apscheduler==3.11.3
gunicorn==26.2.0 (docstring only) pydantic<2.15` (built here). Driver: `$SB/envs/driver`. Ports used: 8720 (full-stack),
8721/8722/8723 (backend-only), Redis 8739. Everything ran from `$SB/apps/verify_pm1` (`EXPECT_VENV` guard in both apps).

## Fixture and scripts (all copied here)
- `apps/forkapp` — unchanged copy of process_model's fixture (import-time `threading.Thread` ticker, `threading.Timer`
  chain, `logging.FileHandler` + `QueueHandler`/`QueueListener`, sqlite engine via `rx.session()`, httpx/asyncio objects,
  sync redis client, module-level `random.random()` / `uuid4()` / `secrets.token_hex()`, a user `random.Random()`
  instance; `/api/whoami`, `/api/log?m=`, ...).
- `apps/otelapp` — NEW: real-world import-time threads: OpenTelemetry SDK `TracerProvider` + `BatchSpanProcessor` and
  `MeterProvider` + `PeriodicExportingMetricReader`, both with FILE exporters (one line per export with the exporting pid,
  no network), `ReflexInstrumentor().instrument(tracer_provider=..., meter_provider=...)` (reflex-otel 0.2.0), an
  APScheduler `BackgroundScheduler` with a 0.5 s interval job, a `QueueListener` logger; `/api/otelstat` reports threads,
  exporter/job counters, `sched.running` vs its thread liveness, queue depth.
- `scripts/serve.sh`, `launch.py`, `probe_run.sh` (`<venv> <label> <prod|prod-be> <port>`: start → wait `/ping` → `tree.py`
  → 60× `/api/whoami` → SIGTERM), `sample_whoami.py`, `tree.py` — process_model's, retargeted to this dir / these ports.
- `scripts/logrun.sh <venv> <label> <port> [K=V...]` — backend-only forkapp, 40× `/api/log`, counts direct vs queued
  log lines per pid, whoami summary, SIGTERM. `scripts/otelrun.sh` — same shape for otelapp with `sample_otel.py`.
- `scripts/fork_semantics.py [fork|spawn]` — pure Python (no reflex): what `fork` does to module constants, the global
  `random` instance, a `random.Random()` instance, `uuid4()`, `secrets`, and a pre-fork thread. `scripts/fork_warn.py` —
  does CPython 3.12 warn when a multi-threaded process forks?
- `scripts/fullstack_chain.sh`, `scripts/chain2.sh` — the exact sequences run (outputs `out/fullstack_chain.txt`,
  `out/chain2.txt`, `out/chain3.txt`).

## Rerun
```bash
export SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa V=$SB/apps/verify_pm1 DEST=<this dir>
mkdir -p $V && cp -r $DEST/apps/* $V/ && cp -r $DEST/scripts $V/ && chmod +x $V/scripts/*.sh
redis-server --port 8739 --save '' --appendonly no &
cd $V && export REFLEX_REDIS_URL=redis://localhost:8739 REFLEX_TELEMETRY_ENABLED=false
./scripts/probe_run.sh new  new-be-fork  prod-be 8721     # 0.10.1a1 backend-only  (out/whoami-new-be-fork.json)
./scripts/probe_run.sh prev prev-be-fork prod-be 8721     # 0.10.0 baseline
./scripts/fullstack_chain.sh                             # full-stack prod 8720, prev then new (builds the frontend)
./scripts/chain2.sh                                      # log-drop / spawn / PYTHONWARNINGS / otel+apscheduler / py3.14 full-stack
./scripts/probe_run.sh process_model-py314-new  py314-new-be  prod-be 8723; ./scripts/probe_run.sh process_model-py314-prev py314-prev-be prod-be 8723
cd $SB && $SB/envs/new/bin/python -I $V/scripts/fork_semantics.py fork; $SB/envs/new/bin/python -I -W default $V/scripts/fork_warn.py
```

## 1. Reproduction matrix (forkapp, Redis → 2×4+1 workers; 0.10.1a1 caps at 8) — `out/whoami-*.json`, `out/tree-*.json`
"imported" = `/api/whoami.imported_in_this_process` (app module executed in the worker); "threads" = import-time ticker /
QueueListener alive in the worker; "module" = distinct module-level `random.random()` across workers; "Random()" = distinct
first draw of the user `random.Random()` instance; "global" = distinct first `random.random()` at request time.

| run | version / Python | mode | workers | imported | threads | module | Random() | global | PSS (python) |
|---|---|---|---|---|---|---|---|---|---|
| new-be-fork | 0.10.1a1 / 3.12 | `--backend-only` | 8 | **0/8** | **0/8** | **1** | **1** | 8 | 213 MB |
| prev-be-fork | 0.10.0 / 3.12 | `--backend-only` | 9 | 9/9 | 9/9 | 9 | 9 | 9 | 691 MB |
| new-prod-full | 0.10.1a1 / 3.12 | full-stack | 8 | 0/8 | 0/8 | 1 | 1 | 8 | 202 MB |
| **prev-prod-full** | **0.10.0 / 3.12** | **full-stack** | 9 | **0/9** | **0/9** | **1** | **1** | 9 | 213 MB |
| py314-new-be | 0.10.1a1 / 3.14 | `--backend-only` | 8 | 0/8 | 0/8 | 1 | 1 | 8 | 222 MB |
| py314-prev-be | 0.10.0 / 3.14 | `--backend-only` | 9 | 9/9 | 9/9 | 9 | 9 | 9 | 921 MB (forkserver) |
| py314-new-full | 0.10.1a1 / 3.14 | full-stack | 8 | 0/8 | 0/8 | 1 | 1 | 8 | 230 MB |
| py314-prev-full | 0.10.0 / 3.14 | full-stack | 9 | 9/9 | 9/9 | 9 | 9 | 9 | 983 MB (forkserver) |
| new-be-log-spawn | 0.10.1a1 / 3.12 + `REFLEX_BACKEND_START_METHOD=spawn` | `--backend-only` | 8 | 8/8 | 8/8 | 8 | 8 | 8 | 696 MB |

All runs: `/ping` up in 2–12 s, 0 tracebacks, 0 `Unexpected exit`, SIGTERM exit 1.5–5 s, 0 leftovers.

→ **Regression scope confirmed exactly as claimed**: 0.10.0 → 0.10.1a1 changes `--backend-only` on 3.12 (fork default: 0.10.0
imported the app per worker because the CLI never imported it; 0.10.1a1 preloads it in the supervisor) and BOTH modes on
3.14 (0.10.0 went through the interpreter's `forkserver` default, so every worker imported the app; 0.10.1a1 forces `fork`).
Full-stack on 3.12 is **unchanged**: 0.10.0's `_run_prod` compiles the app in the CLI process (`_compile_app(avoid_dirty_check=False)`,
`reflex/reflex.py`) and granian 2.8.5 forks workers with `multiprocessing.get_start_method()` (`granian/server/mp.py:52,98`),
so 0.10.0 already forked from a process holding the imported app (0/9 imported, threads dead, 1 distinct value — identical
to 0.10.1a1). 3.11/3.13 should behave like 3.12 (same `fork` default) — not run. macOS/Windows (`spawn` default) are
unaffected by design (`_backend_start_method()` returns None there).

## 2. Refutation attempts
### 2a. "Shares random values / `random.Random()` sequences" — separated precisely (`scripts/fork_semantics.py`, server runs)
Pure Python, 4 forked children (0.10.1a1 venv, no reflex):
```
fork:  distinct_module_random 1, distinct_module_uuid 1, distinct_global_random_now 4, distinct_prng_now 1,
       distinct_prng_seeded_now 1, distinct_uuid4_now 4, distinct_secrets_now 4, ticker_alive_in_children 0
spawn: everything 4 (module re-executed), ticker_alive_in_children 4
```
- Module-level values computed at import (`MODULE_RANDOM`, `MODULE_UUID`, `MODULE_TOKEN`) are identical in every worker —
  **inherent to any preload model** (gunicorn `--preload`, uWSGI default), and already true on 0.10.0 full-stack 3.12.
- The global `random` module instance **is reseeded** in each child: CPython registers `_os.register_at_fork(after_in_child=_inst.seed)`
  (`random.py`, "fork support" block) → `random.random()` at request time is distinct per worker (8 distinct in every server run).
- A user-created `random.Random()` instance is **not** reseeded → identical sequence in every worker (`distinct_first_prng_now: 1`).
  This is standard CPython fork semantics, not a reflex defect; it only affects code that keeps its own `Random()` (jittered
  backoff, sampling, simulations). Nothing security-relevant: `uuid.uuid4()` and `secrets` read `os.urandom` and are distinct
  per request in every worker (`distinct_uuid4_now 4`, `distinct_secrets_now 4`; `uuid_now` differs in every whoami sample).
→ The claim's wording is accurate (module-level values + `Random()` instances); the global `random` module is fine.

### 2b. Import-time threads: dead in children (POSIX fork keeps only the forking thread) — is anything telling users?
- Confirmed in every forked run: `ticker_alive 0/8`, `qlistener_alive 0/8`, `threads` = `["MainThread"]` (+ granian/anyio
  threads), counters frozen at the supervisor's value.
- **Server log (`--loglevel debug`)**: no line mentions the preload or forking (`grep -i "fork|preload" logs/new-be-fork.log`
  → only the app's own `start_method=fork` line). The "spawning workers" fallback (`exec.py`) only fires when a telemetry
  thread is still alive; with telemetry on (process_model §7) it did not fire either.
- **CPython's own warning exists but is hidden by the default filters**: with `PYTHONWARNINGS=default` the supervisor prints
  `/usr/lib/python3.12/multiprocessing/popen_fork.py:66: DeprecationWarning: This process (pid=17673) is multi-threaded, use
  of fork() may lead to deadlocks in the child.` once, right before `Spawning worker-1` (`logs/new-be-log-pywarn.trimmed.log`
  line 75); 0 occurrences in the default run. It fires only when the app actually started threads at import.
- **Docs/changelog**: `docs/hosting/self-hosting.md` (tag v0.10.1a1, lines 53–61) says exactly: "backend workers are forked from a
  supervisor process that has already imported the app ... Set `REFLEX_BACKEND_START_METHOD=spawn` (or `forkserver`) for apps
  that are not fork-safe, for example ones that open database connections or **start threads at import time**." CHANGELOG.md
  v0.10.1a1 lists #7079 under *Performance*: "...forked from a supervisor that has already imported the app... Set
  `REFLEX_BACKEND_START_METHOD=spawn` for apps that are not fork-safe." Neither mentions that this changes `--backend-only`
  / Python 3.14 specifically, the PRNG-instance nuance, or logging/scheduler examples. No upgrade-guide entry (patch release).
- PR #7079 (merged 2026-10-14) describes the fork + preload + `gc.freeze()` design and the telemetry-thread guard; threads
  started by the *app* at import are not discussed beyond the env-var opt-out.

### 2c. Industry context for severity
- Reflex's **own non-granian prod path has always used `gunicorn --preload`** (`run_uvicorn_backend_prod`, identical in
  0.10.0 and 0.10.1a1, `exec.py`): the same preload semantics for `REFLEX_USE_GRANIAN=0` users since before granian existed.
- gunicorn 26.2.0's `preload_app` docstring: "Load application code before the worker processes are forked. By preloading an
  application you can save some RAM resources as well as speed up server boot times. Although, if you defer application
  loading to each worker process, you can reload your application code easily by restarting workers." — gunicorn does not
  warn about threads at all; reflex's self-hosting doc is already more explicit than that. (docs.gunicorn.org / docs.python.org
  are blocked by the sandbox proxy, 403; quotes are from the installed package and CPython source.)
- Difference from gunicorn: there `--preload` is opt-in; in 0.10.1a1 preload is the new Linux **default**, changed in a patch
  release. That is the only real argument for keeping this above "low".

### 2d. `REFLEX_BACKEND_START_METHOD=spawn` — a full workaround? Yes.
`new-be-log-spawn`: 8/8 workers import the app, ticker/Timer/QueueListener alive 8/8, 8 distinct module values and
`Random()` draws, **48/48 queued log records delivered** (8 import lines + 40 API lines), lifespan once per worker, Redis +
sqlite fine, SIGTERM 3.0 s clean. Cost: 696 MB PSS vs 213 MB (= 0.10.0's 691 MB), `/ping` up 3.5 s vs 2.2 s. `forkserver`
behaves the same (process_model §3). The variable is honoured in full-stack mode too (process_model §7b). Invalid values
fail fast with a clear `EnvironmentVarValueError`.

### 2e. Real-world patterns — `out/chain2.txt`, `out/forkapp-*-queued.log`, `out/otel-*.json`, `out/otel-*/**.summary`
| pattern | 0.10.1a1 fork (default) | 0.10.1a1 spawn | 0.10.0 backend-only |
|---|---|---|---|
| `logging.handlers.QueueListener` started at import | **all 40 worker records lost** (`forkapp.log.q` = 1 line, the supervisor's import line; direct `FileHandler` file = 41 lines from 9 pids). The unbounded `queue.Queue` keeps growing in each worker (otelapp `queue_depth` 15 after ~80 requests) → silent log loss **plus** slow per-worker memory growth | 48/48 delivered | 49/49 delivered |
| APScheduler `BackgroundScheduler().start()` at import | **`sched.running` is True in every worker but its thread is dead** (`sched_thread_alive 0/8`, `job_runs` frozen at 1–2 = the supervisor's runs); the job keeps running **once, in the supervisor** | alive 8/8, job advancing 8/8 | ran in all 9 workers (9 duplicate jobs — arguably worse) |
| `threading.Thread` / `threading.Timer` at import | dead, counters frozen | alive | alive |
| **reflex-otel 0.2.0 + opentelemetry-sdk 1.45.1** (`BatchSpanProcessor`, `PeriodicExportingMetricReader`, `ReflexInstrumentor` at import) | **works**: the SDK registers `os.register_at_fork(after_in_child=_at_fork_reinit)` hooks (`opentelemetry/sdk/_shared_internal/__init__.py:117-142`, `metrics/_internal/export/__init__.py:470-484`, `trace/__init__.py:244-254`), so every forked worker has live `OtelBatchSpanRecordProcessor` + `OtelPeriodicExportingMetricReader` threads; `spans.log` has 80 `GET /api/otelstat` spans from **8 distinct worker pids** (+ 8 `reflex.compile` spans), `metrics.log` 5 exports per worker pid; 0 errors in the server log | same | n/a |
| redis-py / SQLAlchemy pools created pre-fork | fine (pid-aware pools; process_model: 288 concurrent writes OK) | fine | fine |

reflex-otel itself starts no thread at import/plugin time (`instrumentor.py` only sets `OTEL_SEMCONV_STABILITY_OPT_IN`
at import; providers come from the app or `_configure_sdk_from_environment()` → the fork-safe SDK). An app that configures
the SDK via `OTEL_TRACES_EXPORTER=otlp` gets the same `BatchSpanProcessor` → same at-fork re-init (exporter network path not
exercised here).

## 3. Severity reasoning
Keeps: silent (by default) loss of a common logging pattern and silently dead schedulers on the documented container path
(`--backend-only`) after a *patch* upgrade; the default changed, not an opt-in. Lowers: identical to what `gunicorn --preload`
(reflex's own uvicorn path) and 0.10.0 full-stack already did; explicitly documented in `self-hosting.md` with the exact
example ("start threads at import time") and a one-line, fully verified opt-out; CPython's at-fork hooks keep the global
`random`, `logging` locks, redis/SQLAlchemy pools and the OpenTelemetry SDK working; `uuid4`/`secrets` unaffected; nothing
crashes or corrupts state; reflex-otel (in the train) is unaffected. → **low** as a framework defect. The actionable items are
release-notes/diagnostics: (1) call out in the 0.10.1 changelog that `--backend-only` on Linux and every prod mode on Python
3.14 now run import-time code once in the supervisor (and that `QueueListener`/scheduler threads, `Random()` instances and
module-level constants are shared/dead in workers); (2) optionally log one line at fork time naming the extra threads alive in
the supervisor (the information CPython already computes for its hidden DeprecationWarning) with the `REFLEX_BACKEND_START_METHOD=spawn`
hint. Not reported as new: none of the other #7079 risks (Redis delivery, DB pools, lifespan, signals) misbehaved here.

## Cleanup
Redis 8739 stopped (pid 13348), every server stopped via SIGTERM (0 leftovers, each run), no listener on 3720-3739 /
8720-8739, `forkapp/.web`, `otelapp/.web` and `node_modules` deleted; `$SB/envs/verify_pm1-otel` left in place (venv).
