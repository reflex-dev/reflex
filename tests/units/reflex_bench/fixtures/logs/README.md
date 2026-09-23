# Captured reflex output

Real output of `reflex run` and `reflex compile`, used as golden input by the
`reflex_bench` driver and collector tests. Captured on Linux (Ubuntu 24.04,
Python 3.14 for HEAD and 3.12 for 0.8.23), merged stdout and stderr, with ANSI
escape sequences stripped. `[...]` marks lines cut from the longer debug logs.

HEAD is reflex `0.9.12.post10.dev0` (this workspace); 0.8.23 comes from PyPI:

```console
$ uv venv -p 3.12 /tmp/r0823 && uv pip install -p /tmp/r0823 reflex==0.8.23
```

Every command ran with this environment (the `reflex-bench` driver sets the same
variables) and was stopped with `SIGTERM` to its process group a few seconds
after the last ready line:

```console
$ export NO_COLOR=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0 REFLEX_USE_GRANIAN=true \
    REFLEX_TELEMETRY_ENABLED=false REFLEX_CHECK_LATEST_VERSION=false
```

## HEAD

```console
$ export PY=$(uv run python -c 'import sys; print(sys.executable)') REFLEX_DIR=/tmp/rb-head/reflex
$ mkdir -p /tmp/rb-head/app && cd /tmp/rb-head/app && $PY -m reflex init --template blank
$ $PY -m reflex compile --loglevel debug                  # head-compile-debug.log (first compile: bun add runs)
$ $PY -m reflex run --env dev --frontend-port 13000 --backend-port 18000         # head-run-dev.log
$ $PY -m reflex run --backend-only --backend-port 18000                          # head-run-backend-only.log
$ $PY -m reflex run --env prod --frontend-port 13000 --backend-port 13000        # head-run-prod.log
$ $PY -m reflex run --env prod --frontend-port 13000 --backend-port 13000 \
    --loglevel debug                                                             # head-run-prod-debug.log
$ $PY -m reflex run --env prod --backend-only --backend-port 18000               # head-run-prod-backend-only.log
```

## 0.8.23

The venv's `bin` directory is on `PATH`, as in an activated venv: 0.8.23 starts
the prod backend as a `granian` command.

```console
$ export PY=/tmp/r0823/bin/python REFLEX_DIR=/tmp/rb-0823/reflex PATH=/tmp/r0823/bin:$PATH
$ mkdir -p /tmp/rb-0823/app && cd /tmp/rb-0823/app && $PY -m reflex init --template blank
$ $PY -m reflex compile --loglevel debug                  # 0.8.23-compile-debug.log (first compile)
$ $PY -m reflex run --env dev --frontend-port 13000 --backend-port 18000         # 0.8.23-run-dev.log
$ $PY -m reflex run --backend-only --backend-port 18000                          # 0.8.23-run-backend-only.log
$ $PY -m reflex run --env prod --frontend-port 13000 --backend-port 18000        # 0.8.23-run-prod.log (sirv + backend)
$ $PY -m reflex run --env prod --frontend-port 13000 --backend-port 18000 \
    --loglevel debug                                                             # 0.8.23-run-prod-debug.log
$ $PY -m reflex run --env prod --backend-only --backend-port 18000               # 0.8.23-run-prod-backend-only.log
```

`0.8.23-run-prod-granian-not-on-path.log` is the prod command run without the
venv on `PATH`: the backend crashes, yet both ready lines are printed after the
traceback, and nothing listens on port 18000.
