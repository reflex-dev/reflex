# orch_otel — reflex-otel 0.1.0 on reflex 0.9.12a1: the initial dev `reflex.compile` span tree (#7155)

Changelog line under test (reflex and reflex-base): "Flush OpenTelemetry compile spans before the isolated
initial development compile worker exits. (#7155)". The previous campaign (0.9.11a1, FINDING-028 →
issue #7095) found that under dev `reflex run` the initial compile runs in a `ProcessPoolExecutor` worker
that exits via `os._exit`, so the `reflex.compile` tree with `trigger=initial` never reached the exporter
(or arrived as orphaned stage children).

Venv: `cd $SB && uv venv envs/otel --python 3.11 && uv pip install --python envs/otel/bin/python --prerelease=allow 'reflex==0.9.12a1' <component alphas> 'reflex-otel==0.1.0' opentelemetry-sdk opentelemetry-exporter-otlp-proto-http`
→ reflex 0.9.12a1, reflex-base 0.9.12a1, reflex-otel 0.1.0, opentelemetry-sdk/api 1.44.0.

App: `otelapp/` is the previous campaign's otel sample app unchanged (`OTEL_TEST_MODE=programmatic` wires
a JSONL span/metric exporter per process under `$OTEL_DUMP_DIR`; `GET /otel/flush` force-flushes).
Runner: `run_otel_probe.sh` (ports 3052/8052): dev first run (bun install + compile), dev second run,
and `reflex export --frontend-only` as the in-process control; each case drives one page load in
Chromium via `drive_app.py`, flushes, waits 6 s, stops the server and prints the span forest
(`scripts/spantree.py`) plus an orphan check.

## Result — dev first run (`dumps/dev_initial/`, `logs/dev_initial-spantree.txt`)

| process | spans | content |
|---|---|---|
| compile worker (pid 5393, `spans-5393.jsonl`) | 4 | `reflex.compile` **`trigger=initial`** with children `reflex.compile.pages`, `reflex.compile.install_frontend_packages`, `reflex.compile.write` |
| backend worker (pid 5429) | 5 | `reflex.compile trigger=backend_startup`, `hydrate`, `on_load_internal`, `HTTP /_event/`, `GET /otel/flush` |

9 spans, **0 orphans**, every stage child's parent exported. → **#7155 verified: the initial compile tree
is now exported from the isolated dev compile worker** (previous behavior: lost or orphaned).
Browser: 0 console/page/network anomalies on the page load (`logs/dev_initial-drive.json`).

Runner quirk (mine, not reflex): the first version of `run_otel_probe.sh` cleaned up leftover
processes with `ss -ltnp`, which is not installed in this container, so the first run's server kept
3052/8052 bound and the second dev case could not start; the script now uses `tools/ports.py`. The
second dev case and the export control were re-run afterwards — see below.

## Result — dev second run (`dumps/dev_second/`, `logs/dev_second-spantree.txt`)

Frontend already compiled once (bun packages installed): the compile worker (pid 7312) again exported the
full `reflex.compile trigger=initial` tree with `pages` / `install_frontend_packages` / `write` children,
the backend worker (pid 7342) its `backend_startup` tree; 9 spans, 0 orphans. Frontend 200 in 2 s.

## Result — `reflex export --frontend-only` (control, `dumps/export/`)

In-process compile: one `reflex.compile trigger=export` tree, as before.

## Result — dev hot reload (`dumps/dev_hot/`, `logs/dev_hot-spantree.txt`)

See the appended section below (re-run after a runner path bug; the edit is applied with an absolute path).

### Hot reload (re-run, `dumps/dev_hot/`, `logs/dev_hot-spantree.txt`, `logs/probe_run3_hot_output.txt`)

Dev server up, then `sed` the heading in `otelapp/otelapp.py` → granian "Changes detected, reloading
workers.." → a new worker (pid 8267) exported a complete `reflex.compile trigger=hot_reload` tree with the
three stage children, alongside the `initial` tree from the compile worker (pid 8204) and the
`backend_startup` tree (pid 8233). 0 orphans.

## Verdict

#7155 holds on the published packages: every compile trigger kind (`initial`, `backend_startup`,
`hot_reload`, `export`) exports a complete, parented `reflex.compile` tree with reflex-otel 0.1.0 on
reflex 0.9.12a1. The previous campaign's FINDING-028 (issue #7095) is fixed. No anomalies in the server
logs or browser console across the four runs.
