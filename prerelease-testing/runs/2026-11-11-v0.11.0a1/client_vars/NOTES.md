# client_vars cluster — reflex 0.11.0a1 (2026-11-11)

## Status / resume here
- Working dir: `$SB/apps/client_vars/` (`SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`).
  Ports: frontend 3260-3279, backend 8260-8279. Venvs: shared `new` (0.11.0a1), `prev` (0.10.1), `driver`.
- Helper: `scripts/srv.sh start <label> <venv> <dev|prod> <appdir> <fport> <bport> [ENV=VAL...]` / `srv.sh stop <label>`
  (own process group, refuses busy ports, logs in `$W/logs/<label>.log`). Drivers run with
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/<driver>.py ...`.
- DONE so far: client_state app `csapp` dev + prod on `new` (91/91 checks, console clean).
- IN PROGRESS: client_state under `auto_memoize=False` + `react_compiler=True`; overkey prev vs new.
- TODO: SetVar app, storage declarations + multi-tab + hydration fixtures, var error probes, unicode, final report.

## 1. client_state (#6936)

### Offline probe (`probes/cs_probe.py`)
`cd $SB/apps/client_vars/probes && $SB/envs/new/bin/python -I cs_probe.py new`

### App `csapp` (pages `/`, `/other`, `/memo`, `/backend`, `/legacy`)
```
cd $SB/apps/client_vars
scripts/srv.sh start cs-dev new dev $PWD/csapp 3260 8260
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_cs.py http://localhost:3260 new-dev
scripts/srv.sh stop cs-dev
scripts/srv.sh start cs-prod new prod $PWD/csapp 3261 3261     # prod: one port
... drive_cs.py http://localhost:3261 new-prod
```
Results (0.11.0a1): dev 91/91, prod 91/91, browser console clean (prod: only the favicon 404).
