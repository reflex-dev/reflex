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
