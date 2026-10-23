# Cluster `process-model` — backend start method, workers, signals, app loading

## Changelog lines (verbatim)
- (reflex #7079, PERF) Production backend workers on Linux are now forked from a supervisor that has already imported the app, so they share its memory instead of each importing the app again. Set `REFLEX_BACKEND_START_METHOD=spawn` for apps that are not fork-safe.
- (reflex-base #7079) Add the `REFLEX_BACKEND_START_METHOD` environment variable to choose how production backend workers are started (`fork`, `spawn`, or `forkserver`).
- (reflex #7113, PERF) The `reflex run` backend reload worker is now forked from the supervisor on Linux instead of started through a forkserver. Set `REFLEX_BACKEND_START_METHOD=spawn` or `REFLEX_STRICT_HOT_RELOAD=1` for apps that are not fork-safe.
- (reflex #7542) Cap the automatically selected number of Redis-backed backend workers at eight. Set `GRANIAN_WORKERS` to override the default.
- (reflex #7538) `reflex run` no longer logs "Unexpected exit from worker-1" when the dev backend is stopped with SIGTERM or SIGINT.
- (reflex-base #7558) On POSIX, `reflex run --json` forwards SIGINT to its child process, so supervisors that signal only the Reflex PID can stop the app cleanly.
- (reflex #7258) Load backend apps by their configured module name so state updates work even when the app package has no `__init__.py`.

## What to build
A plain app whose module records, at import time, the PID, `multiprocessing.get_start_method()`, and a timestamp to a log file, and whose `on_load` records the worker PID. Run it in: dev (`reflex run`), prod (`reflex run --env prod`), with `REFLEX_BACKEND_START_METHOD` unset / `fork` / `spawn` / `forkserver`, with `REFLEX_STRICT_HOT_RELOAD=1`, with `GRANIAN_WORKERS=3` in prod. For each: process tree (`ps -o pid,ppid,cmd --forest`), how many times the app module imported, memory (RSS of workers, `ps -o rss`), startup time to first 200. Stop each with SIGINT and SIGTERM (to the `reflex` PID, and to the process group) and read the shutdown log: no "Unexpected exit from worker-1", no tracebacks, all children gone (`ps`). With `--json`: send SIGINT only to the reflex PID and confirm the child exits.
Module-name loading: an app package dir WITHOUT `__init__.py` (delete it after `reflex init`) and one with `app_name` differing from the directory name via `rxconfig.py` — state updates must work end-to-end in the browser (click a counter), in dev and prod.
Fork-safety: app that opens a sqlite connection/thread/`asyncio` loop at import time — run default (fork) vs spawn and record any difference; a hang or traceback under the default is a finding to document (the docs say to set spawn, so check that the failure mode is at least diagnosable).
Hot reload under fork (dev): edit the app source while running; confirm reload works and the reload worker is a fork (ppid = supervisor), no forkserver process in the tree; compare with 0.10.0's tree.

## Combine it with
- Redis: if `redis-server` is available (`which redis-server`), start one on a private port and set `REFLEX_REDIS_URL`; confirm worker count auto-select caps at 8 on this 4-CPU box (it will likely pick fewer; set `GRANIAN_WORKERS=12` to prove override) — otherwise record skipped.
- Uvicorn backend (`rxconfig` or env to pick uvicorn if the published version supports it) must ignore the start-method variables without warnings.
