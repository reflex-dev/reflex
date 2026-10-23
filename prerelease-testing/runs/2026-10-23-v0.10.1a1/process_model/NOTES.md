# process_model — reflex 0.10.1a1 (#7079 #7113 #7542 #7538 #7558 #7453 #7052 #7304, lifecycle, Redis multi-worker, CLI-16, EVT-04)

Venvs: `$SB/envs/new` = reflex 0.10.1a1 (Python 3.12.3, granian 2.8.5, redis 7.4.1, sqlalchemy 2.1.6), `$SB/envs/prev` = 0.10.0 (same
deps), `$SB/envs/driver` (playwright). Ports 3200-3219 / 8200-8219; Redis on 8219 (`redis-server --port 8219 --save '' --appendonly no`).
Work dir `$SB/apps/process_model` (`PM`). Everything here runs from a copy; apps assert `EXPECT_VENV`.

## Apps and scripts (all in this directory)
- `apps/forkapp` — fork-safety app (see its docstring): at import it starts a `threading.Thread` ticker and a `threading.Timer`
  chain, a `logging.FileHandler` and a `QueueHandler`+`QueueListener` (thread), creates the `rx.Model` table + queries it via
  `rx.session()` (engine pool connection established before the fork), `httpx.AsyncClient`/`asyncio.Lock`/`asyncio.Queue`,
  a sync `redis.Redis` client (pinged), module-level `random.random()`/`uuid4()`/`secrets`, a user `random.Random()` instance;
  `register_lifespan_task`, `api_transformer` routes `/api/whoami`, `/api/dbwrite`, `/api/log`, `/api/fetch`,
  `POST /api/poke/<token>` (`app.modify_state` from an arbitrary worker = EVT-04), a background event, DB writes from events.
- `scripts/serve.sh start <venv> <appdir> <label> <dev|prod|prod-be|dev-be> <ports> [args]` / `wait <url>` / `stop <label> [SIG]`
  (detached via `scripts/launch.py`, pid in `run/<label>.pid`, log in `logs/<label>.log`, `--loglevel debug`).
- `scripts/tree.py <pid>` process tree with RSS/PSS; `scripts/sample_whoami.py <base> [n]` per-worker aggregation of `/api/whoami`;
  `scripts/drive_forkapp.py <base> <out.json> --clients 6` Playwright: 6 isolated contexts, poke each token over HTTP, expect
  `poked: 1` on every page, then inc/note/bg/fetch/reload per client, console capture; `scripts/dbstress.py` 24 threads x 12
  `/api/dbwrite`; `scripts/hot_reload.py` dev hot-reload sequence (see below); `scripts/copy_to_dest.sh`.

## Rerun
```bash
export SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa PM=$SB/apps/process_model DEST=<this dir>
mkdir -p $PM && cp -r $DEST/apps/* $PM/ && cp -r $DEST/scripts $PM/ && chmod +x $PM/scripts/*.sh
redis-server --port 8219 --save '' --appendonly no &
cd $PM && REFLEX_REDIS_URL=redis://localhost:8219 ./scripts/serve.sh start new $PM/forkapp new-prod-redis prod 8200 && ./scripts/serve.sh wait http://localhost:8200/ping
$SB/envs/driver/bin/python -I scripts/tree.py $(cat run/new-prod-redis.pid)
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python -I scripts/sample_whoami.py http://localhost:8200 80
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python -I scripts/drive_forkapp.py http://localhost:8200 out/drive.json --clients 6
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python -I scripts/dbstress.py http://localhost:8200 24 12
./scripts/serve.sh stop new-prod-redis TERM      # or INT
```
(Same with `prev` for the baseline.)

## Issues (details in the sections below)

### ISSUE-1 (medium, regression for `--backend-only` / Python 3.14; documented as intentional): import-time threads are silently dead in forked prod workers, module-level values and user PRNG instances are shared
`reflex run --env prod --backend-only` (0.10.1a1, Linux, default `fork`) imports the app once in the supervisor and forks the
workers. Every thread the module started at import (`threading.Thread`, `threading.Timer`, `logging.handlers.QueueListener`,
APScheduler-style schedulers) exists only in the supervisor: in each worker `Thread.is_alive()` is False, counters never
advance, and **every record logged through a `QueueHandler` from a worker is dropped** (`out/forkapp-new-queued.log` holds one
line, from the supervisor; the direct `FileHandler` file holds all 30 worker lines). Module-level `random.random()`, `uuid4()`,
`secrets.token_hex()` evaluate once (identical in all 8 workers) and a user-created `random.Random()` instance yields the same
sequence in every worker (`distinct_first_prng_now: 1`). On 0.10.0 the same command ran the module once per worker
(`imported_in_worker 9/9`, threads alive 9/9, 9 distinct values) — on Python 3.12 and 3.14 alike. Full-stack
`reflex run --env prod` on Python 3.12 already behaved like this on 0.10.0 (the CLI process imports the app for the compile
and forks), so the regression is limited to `--backend-only` (the documented container path) and to Python 3.14 (forkserver
before). Nothing is logged. The changelog and `docs/hosting/self-hosting.md` say "set `REFLEX_BACKEND_START_METHOD=spawn`
for apps that are not fork-safe, for example ones that open database connections or start threads at import time", so this
is a known trade-off; reported because the failure mode is silent (logging via a queue listener vanishes) and because the
upgrade guide / changelog do not mention the PRNG / module-constant sharing. `spawn` restores 0.10.0 behaviour at 0.10.0's
memory cost (701 MB vs 200 MB PSS for 8 workers).
Repro: section 2 (`scripts/probe_run.sh new new-be-fork prod-be 8201` vs `prev`), `out/whoami-{new,prev}-be-fork.json`.

## Results

### 1. Prod + Redis, full stack (`reflex run --env prod --frontend-port 8200 --backend-port 8200`)
| | new 0.10.1a1 | prev 0.10.0 |
|---|---|---|
| workers (4 CPUs, Redis) | **8** (`[INFO] Spawning worker-1..8`; #7542 cap) | 9 (2*4+1) |
| granian "more workers than CPU cores" warning | yes (benign) | yes |
| tree PSS (python, after driver) | 204.7 MB (supervisor ~32 MB + 8 x ~22 MB) | 237.6 MB (supervisor + 9 x ~22 MB) |
| per-worker PSS | ~22 MB | ~22 MB |
| `/ping` up after start (frontend already built) | 8 s | 13 s |
| `multiprocessing.get_start_method()` in workers | fork | fork |
| app imported in worker? (`/api/whoami imported_in_this_process`) | **no, 0/8** (import pid = supervisor) | **no, 0/9** (same: `_run_prod` compiles in-process, py3.12 forks) |
| module-level `random.random()` / `uuid4()` | 1 distinct value across 8 workers | 1 distinct across 9 |
| `random.random()` after fork | 8 distinct (CPython reseeds the global instance at fork) | 9 distinct |
| user `random.Random()` instance first value | **identical in every worker** | identical |
| import-time `threading.Thread` ticker / `Timer` | dead in every worker (`ticker_alive false`, counters frozen at the supervisor's value, thread list = `MainThread`) | same |
| import-time `QueueListener` logging thread | dead: `forkapp.log.q` has only the supervisor's import line, 0 of 30 worker lines (direct FileHandler: 30/30 across all workers) | same |
| lifespan task | runs once per worker | same |
| sync redis client created+pinged pre-fork | works in every worker (redis-py pid check) | same |
| sqlite engine with a pre-fork pooled connection, 288 concurrent `/api/dbwrite` over all workers | 288 ok, 0 errors, count 294 (= 288 + 6 UI notes) | 288 ok, 0 errors |
| EVT-04 (6 clients, `POST /api/poke/<token>` from arbitrary workers) | **6/6 delivered, 6/6 cross-worker** (2 rounds) | 6/6, 6/6 cross-worker |
| inc / note(db) / bg / fetch(self httpx) / reload per client | 6/6 each | 6/6 each |
| console | clean except the favicon 404 | same |
| SIGTERM to the supervisor | exits in 1.3-2.0 s, 0 leftovers, no "Unexpected exit" | (see below) |
| SIGINT to the supervisor | exits < 1 s, 0 leftovers | |
| `kill -9` one worker | **the whole server shuts down**: `[ERROR] Unexpected exit from worker-1` → `Shutting down granian` → all 8 workers stopped → `Reflex app stopped`; port closed (granian default `respawn_failed_workers=False`) | identical (worker-1 killed → all 9 stopped → app stopped) |

Both versions behave the same here because `_run_prod` compiles the app in the CLI process (`_compile_app(avoid_dirty_check=False)`),
so on Python 3.12 (Linux default `fork`) 0.10.0 already forked workers from a process holding the imported app. Note
`start_method_at_import` is `None` on 0.10.1a1 too: the import happens during the compile, before `run_granian_backend_prod`
sets the start method, so the "set before the preload" comment in `exec.py` only applies to `--backend-only`.

### 2. Prod **backend-only** + Redis (`reflex run --env prod --backend-only --backend-port 8201`) — the container deployment path
`scripts/probe_run.sh <venv> <label> prod-be 8201` (start, wait, tree, whoami x60, SIGTERM). Results `out/whoami-*.json`, `out/tree-*.json`.
| | new 0.10.1a1 (fork, default) | prev 0.10.0 |
|---|---|---|
| `/ping` up | 2.2 s wall | 3.2 s wall |
| workers | 8 | 9 |
| tree PSS (python) | **200 MB** (8 workers ~21 MB + supervisor) | **693 MB** (9 workers ~70 MB each: every worker imports the app) |
| app imported in worker | 0/8 (preloaded in supervisor pid) | **9/9** |
| import-time `threading.Thread` ticker alive in worker | **0/8** (counter frozen) | 9/9, advancing |
| import-time `threading.Timer` chain | dead in workers | alive in every worker |
| import-time `QueueListener` logging thread | **0/8 alive** → every `qlog.info()` from a worker is silently lost | 9/9 alive |
| module-level `random.random()` / `uuid4()` / `secrets.token_hex()` | **1 distinct value across 8 workers** | 9 distinct (one per worker) |
| user `random.Random()` instance first draw | **identical in all 8 workers** | 9 distinct |
| global `random.random()` after fork | distinct per worker | distinct |
| lifespan task | once per worker | once per worker |
| SIGTERM | 1.5 s, 0 leftovers, 0 "Unexpected exit" | 2.5 s, 0 leftovers |
→ This is the #7079 behaviour change in its documented form ("Set `REFLEX_BACKEND_START_METHOD=spawn` for apps that are not
fork-safe"); 0.10.0 ran module-level code once per worker in this mode, 0.10.1a1 runs it once in the supervisor. See ISSUE-1.

### 3. `REFLEX_BACKEND_START_METHOD` matrix, `GRANIAN_WORKERS`, memory manager (backend-only prod, new unless noted)
| run | workers | up | PSS python | imported in worker | threads alive | distinct module random | notes |
|---|---|---|---|---|---|---|---|
| `fork` (default, Redis) | 8 | 2.2 s | 200 MB | 0/8 | 0/8 | 1 | `start_method` in worker = fork |
| `spawn` (Redis) | 8 | 4.3 s | 701 MB | 8/8 | 8/8 | 8 | workers import the app; = 0.10.0 behaviour (0.10.0: 693 MB) |
| `forkserver` (Redis) | 8 | 4.3 s | 701 MB | 8/8 | 8/8 | 8 | +1 forkserver process in the tree (10 procs) |
| `bogus` (invalid) | — | fails at once | — | — | — | — | `EnvironmentVarValueError: Invalid literal value: 'bogus' for REFLEX_BACKEND_START_METHOD, expected one of ('fork', 'spawn', 'forkserver')`, then `Info: Reflex app stopped.` rc≠0 — clear (traceback printed) |
| `GRANIAN_WORKERS=12` (Redis) | **12** | 2.1 s | 243 MB | 0/12 | 0/12 | 1 | override above the cap honoured |
| memory manager (no Redis) | 1 | 2.1 s | 106 MB | 0/1 | 0/1 | 1 | prev: 1 worker, 120 MB, imported in worker, threads alive |
All runs: SIGTERM exit 1.5-3.0 s, 0 leftovers, 0 `Unexpected exit`, 0 tracebacks (`logs/new-be-*.trimmed.log`).

### 4. Dev hot reload (#7113) — `scripts/hot_reload.py <venv> <appdir> 3202 8202 out/hot-<label>.json [--env K=V]`
Fresh copy of `apps/hotapp` (+ a `/api/pid` route injected by the driver), `reflex run --loglevel debug`, Chromium on `/`.
Sequence: bump → edit handler constant (v2) → edit `helper.py` (h2) → add a state var + `/about` page with a new state →
break `hotapp.py` (SyntaxError), probe the backend port 6x while broken (CLI-16) → fix → edit `rxconfig.py` (`qa_marker`) →
edit again (v4) → SIGTERM. Results `out/hot-*.json`, full server logs `out/hot-*.json.server.log`.
| check | new (fork, default) | new `REFLEX_STRICT_HOT_RELOAD=1` (spawn) | prev 0.10.0 (fork) |
|---|---|---|---|
| backend up | 4.5 s | 3.7 s | see json |
| worker replaced after a handler edit | 0.30 s | 1.66 s | |
| helper-module edit visible | yes (0.41 s) | yes (1.47 s) | |
| new var + new page + new state | render and work (0.33 s) | work (1.29 s) | |
| **CLI-16** port while the module is broken | `refused` instantly on all 6 probes (0.00 s), no hang; recovers 0.5 s after the fix | refused instantly; recovers 1.2 s | |
| `rxconfig.py` edit | worker restarts (0.28 s) but **`cfg=none`: the forked worker keeps the supervisor's cached `rxconfig` module** | **picked up** (`cfg=cfg2`) | |
| console warnings during reloads | #7553 "built for another version ... state schema" banner + #7435 "Skipping state update for unknown substate(s) ... about_state" while the frontend rebuilds after the add-page edit (transient, page recovers) | same two warnings | |
| SIGTERM | exits 0.27 s, 0 leftovers, port refused | 0.86 s, one momentary `<defunct>` python | |
| `Unexpected exit from worker-1` in the log | once, immediately after the SyntaxError crash (a real crash); **none at shutdown** (#7538 OK) | same | |
| state (`count`) across reloads | kept (2 after the first reload) | kept | |
prev 0.10.0 (fork): identical to new/fork — reloads 0.28-0.68 s, CLI-16 refused instantly, recovers 0.5 s, `rxconfig.py` edit NOT
picked up (`cfg=none`) → the rxconfig limitation is pre-existing (the supervisor imports `rxconfig` and the forked worker keeps
the cached module; 0.10.0 on Python 3.12 forks too). prev's console shows the old *error* `Cannot process state update: no
dispatch function for substate(s) ... about_state` during the add-page reload where new shows the #7435 *warning*.
new + Redis (`--env REFLEX_REDIS_URL=redis://localhost:8219`, `out/hot-new-redis.json`): same results as new/memory (18/20,
reloads 0.27-0.33 s, CLI-16 refused instantly, rxconfig not picked up).

### 5. #7052 atomic + locked `reflex.json` writes — `scripts/json_lock_probe.py <venv> <workdir> 8 40 [--reflex-dir DIR]`
8 spawned processes x 40 `path_ops.update_json_file(<workdir>/reflex.json, {unique_key: pid})` (installed reflex) + a reader
re-parsing the file every 2 ms. `out/jsonlock-results.txt`.
| | keys present / 320 | reader invalid parses | tmp files left | |
|---|---|---|---|---|
| new, default `REFLEX_DIR` (`~/.local/share/reflex/locks` sidecar) | **320 / 320** | 0 / 296 reads | none | 1.1 s |
| prev 0.10.0 | a writer crashes: `json.decoder.JSONDecodeError: Extra data: line 1 column 470` (read-modify-write race on a partial file) | | | the bug #7052 fixes |
| new, `REFLEX_DIR/locks` is a regular file (lock dir cannot be created) | 121 / 320 (updates overwrite each other) | 0 / 176 | none | documented fallback: "writes remain atomic but concurrent updates may overwrite each other"; logged at debug only |
| new, read-only `REFLEX_DIR` (`chattr +i`) | 99 / 320 | 0 | none | same documented fallback |

### 6. STATE-36 / #7304 — app package without `__init__.py` (`apps/noinit`, `scripts/drive_noinit.py`)
`serve.sh start <venv> $PM/noinit noinit-<v>-<mode> dev 3204:8204` (prod: `prod 8204`), then
`drive_noinit.py http://localhost:3204 out/noinit-<label>.json`: hydrated, on_load delta, 2 clicks, substate handler, reload, console.
| | new dev | new prod | prev dev (positive control) |
|---|---|---|---|
| result | **7/7 pass**, console clean, no "no dispatch function" | **7/7 pass** | **0/7**: `hydrated: no`, no on_load delta, clicks do nothing; console `Cannot process state update: no dispatch function for substate(s) "reflex___state____state.noinit____state", "...noinit____other"`; server log `[Reflex Frontend Exception] ... State update failed: no dispatch function` (`logs/noinit-prev-dev.trimmed.log`) |
→ STATE-36 **fixed** (#7304 loads the backend app by its configured module name instead of a file path; granian no longer
derives `noinit` instead of `noinit.noinit`). Note the merged change is the module-name target only; the PR text's "raises a
clear error pointing at the missing file" is not what shipped (and is not needed: the layout now simply works).

### 7a. Python 3.14 (where #7079 / #7113 change the most: the interpreter default is `forkserver`)
Venvs `$SB/envs/process_model-py314-{new,prev}` (`uv --no-config venv --python 3.14` + `reflex[db]==<ver> 'pydantic<2.15'`, Python 3.14.6).
Backend-only prod + Redis (`probe_run.sh process_model-py314-<v> py314-<v>-be-fork prod-be 8201`):
| | new 0.10.1a1 | prev 0.10.0 |
|---|---|---|
| tree | supervisor (35 MB) + 8 forked workers (~26 MB each) = **252 MB PSS**, 9 procs | supervisor 56 MB + resource tracker 7 MB + forkserver 109 MB + 9 workers ~100 MB each = **981 MB PSS**, 11 procs |
| `/ping` up | 8.3 s | 9.6 s |
| app imported in worker / threads alive / QueueListener alive | 0/8 / 0/8 / 0/8 | 9/9 / 9/9 / 9/9 (`start_method` in worker: spawn-style via forkserver) |
| SIGTERM | 2.0 s, clean | 4.0 s, clean |
So on 3.14 the behaviour change is the same as on 3.12 `--backend-only` (ISSUE-1), with a 4x memory win.

Dev on 3.14 (`serve.sh start process_model-py314-<v> $PM/hotapp py314-<v>-devbe dev-be 8205`, `out/tree-py314-*-devbe.json`):
new = 2 python processes (supervisor 51 MB + forked worker 51 MB PSS, 102 MB total); prev = 3 (supervisor 43 MB + a 1-thread
multiprocessing helper 9 MB + worker 64 MB, 116 MB). Hot-reload sequence on py3.14 new (`out/hot-py314-new.json`): 18/20,
identical to 3.12 (reloads 0.3-0.58 s, CLI-16 refused instantly, recovers 0.4 s, rxconfig edit not picked up, the two
transient #7553/#7435 warnings), SIGTERM 0.26 s clean.

### 7b. Full-stack prod with `REFLEX_BACKEND_START_METHOD=spawn` (new) — the documented opt-out
`REFLEX_BACKEND_START_METHOD=spawn REFLEX_REDIS_URL=... serve.sh start new $PM/forkapp new-prod-spawn prod 8200`: up in 17 s,
index 200 (the compiled frontend is mounted in spawned workers too: `EnvVar.set` writes `os.environ`), 8 workers each importing
the app (`imported_in_worker 8/8`, ticker/QueueListener alive 8/8, 8 distinct module values), drive 24/25 (favicon 404 only),
EVT-04 4/4 delivered (3/4 cross-worker), SIGTERM clean, 0 tracebacks. `out/drive-new-prod-spawn.json`, `out/whoami-new-prod-spawn.json`.

### 8. Lifecycle fixtures (`fixtures/upgrade/lifecycle`, staged at `$PM/lifecycle` with `$PM/bin/env.sh`)
`cd $PM/lifecycle && FP=3210 BP=8210 QA_EOF_CAP=40 QA_WAIT_CAP=20 W=$PM bash bin/json_matrix.sh <label> <venv> INT-group:40 TERM-pid:40 TERM-pid:6 INT-pid:40`
(A3-07 = CLI-26 `--json` ignores a pid-only SIGINT, A3-08 = CLI-27 30 s drain cap truncates the last record). Results in
`lifecycle/out/jsondrain/<label>-<sig>-r<rate>.json` (copied to `out/`). Expected on 0.10.0 (README): INT-group/TERM-pid at 40
lines/s exit ~6-7 s, 0 lost; TERM-pid at 6 lines/s exits at the 30 s cap with a truncated last record; INT-pid never exits.
| spec | new 0.10.1a1 | prev 0.10.0 / a3 record |
|---|---|---|
| INT-group:40 | exit 6.5 s rc 0, 1139 lines, 0 invalid, last line valid, 0 lost, 0 gaps, no leftovers | a3: ~6-7 s, 0 lost |
| TERM-pid:40 | exit 7.1 s rc 0, 1257 lines, 0 invalid, 0 lost, no leftovers | a3: ~6-7 s, 0 lost |
| TERM-pid:6 (A3-08 / CLI-27) | exits at the 30 s cap (30.66 s) rc 0, **last record truncated** (`invalid_json 1`, "Extra data"), 225 records lost | **unchanged** (a3: same; filed-open reflex#7510) |
| INT-pid:40 (A3-07 / CLI-26, #7558) | **exits 8.9 s after a pid-only SIGINT**, rc 0, 786 lines, 0 invalid, 0 gaps, no leftovers → **fixed** | a3/0.10.0: never exits (killed at the cap); prev control below |

### 7. Telemetry enabled (default for users) + backend-only prod, new
`REFLEX_TELEMETRY_ENABLED=true scripts/probe_run.sh new new-be-telemetry prod-be 8201`: up in 2.2 s (same as with telemetry off),
8 forked workers, no "spawning workers" fallback in the debug log, 0 tracebacks. The `_shutdown_executor` drain did not delay
startup in this sandbox (outbound HTTPS goes through a proxy, so the posthog send does not stall on DNS here).
