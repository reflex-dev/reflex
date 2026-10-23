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
| `kill -9` one worker | **the whole server shuts down**: `[ERROR] Unexpected exit from worker-1` → `Shutting down granian` → all 8 workers stopped → `Reflex app stopped`; port closed (granian default `respawn_failed_workers=False`) | same (see below) |
