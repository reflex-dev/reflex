# server_net — reflex 0.11.0a1 (CORS, lifespan/api_transformer, routes, hydration, CLI shutdown/ports, blocking monitor, otel, hosting-cli)

## Status / resume here
- In progress. Done: harness, prod same-origin smoke, signal shutdown prod (INT group / TERM pid / INT pid, new vs prev).
- Next: dev signals + --json, lifespan matrix, CORS split-origin matrix, routes, HYD-06, #7621, #7653, blocking monitor, otel, hosting-cli.

## Setup (reproduce)
```
export SB=<scratchpad>; export W=$SB/apps/server_net
# own venvs (PyPI only, cwd $SB): reflex[db] + fastapi + uvicorn, siblings pinned to the shared venv's freeze
cd $SB && uv --no-config venv $SB/envs/server_net-main --python 3.12 && \
  uv --no-config pip install --python $SB/envs/server_net-main/bin/python --prerelease=allow --only-binary :all: \
  -c new_constraints.txt 'reflex[db]==0.11.0a1' fastapi uvicorn        # new_constraints = pip freeze of $SB/envs/new
cd $SB && uv --no-config venv $SB/envs/server_net-prev --python 3.12 && \
  uv --no-config pip install --python $SB/envs/server_net-prev/bin/python --only-binary :all: \
  -c prev_constraints.txt 'reflex[db]==0.10.1' fastapi uvicorn          # prev_constraints = pip freeze of $SB/envs/prev
```
- App: `src/netapp` (copy in this dir). Env knobs documented in `src/netapp/netapp/netapp.py` docstring
  (`NA_VENV` guard, `NA_LOG` marks file, `NA_TX` transformer variant, `NA_CASE_DUP`, `NA_EXTRA`, `NA_TASK_FAIL`,
  `NA_TRANSPORT`, `NA_CFG_*_PORT`, `NA_CFG_BLOCK_THRESHOLD`).
- `bin/srv.sh start <label> <venv> netapp <reflex run args>` syncs `src/netapp` to `$W/run/<venv>/netapp` and starts it
  in its own session; `bin/srv.sh stop <label>`; `bin/srv.sh wait <url>`.
- `bin/sigtest.sh <label> <venv> <dev|prod|prod-be|dev-be> <INT|TERM> <group|pid>` = start, signal, report exit time,
  leftover group members, listening ports, and the lifespan marks.
- Driver: `NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drivers/drv.py <base> <basic|connect|routes|big|block> out.json`.

## Checks
### prod same-origin smoke (single port 3340, server_net-main)
- `drv.py http://localhost:3340 basic`: 11/11 — load, inc, on_load index/about, client nav to `/About` (router path
  `/about`, on_load ran), `/items/A1`, `/ITEMS/b2` (on_load ran with params id=b2, router path `/items/[id]`), upload,
  `rx.download(data=...)`, `rx.download(url=get_upload_url(...))`. Console only a favicon 404.
- anomaly (benign?): the `starlette_app` passed to a lifespan task lists routes
  `/ping, /_health, /_event, /_upload x4, ""` — `/_upload` appears 4 times (POST route + mount, twice). TODO compare prev.
- note: `router.page.path` for `/` is `/index` (check prev).

### signals, prod (`bin/sigtest.sh`, 3342)
| venv | INT->group | TERM->pid | INT->pid |
|---|---|---|---|
| 0.11.0a1 | exits 0.25 s, lifespan stop marks, nothing left | same | same |
| 0.10.1 | same | same | same |
