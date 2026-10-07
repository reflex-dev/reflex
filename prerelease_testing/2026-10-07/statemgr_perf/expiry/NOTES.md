# Memory/disk expiry, persistence and session churn

Completed on published 0.10.0a2 and 0.9.12, macOS26.6.2 arm64. Alpha2 correctly removes expired disk-session locks, including after300 short-lived browser sessions; stable retains them. Ordinary post-expiry browser recovery works in both versions. A released background task has a **pre-existing stale-view anomaly** described separately below. No new alpha2 regression established.

Owned scope is `statemgr_perf/expiry/`, ports3260–3267/8260–8267. Parent owns Redis and timing benchmarks. All execution used neutral scratch `/private/tmp/reflex-prerelease-macos-pass2`, uv, and read-only PyPI environments. No framework fixes, private state overrides, shared environment installs or Git/board operations.

## Fixture and verified configuration

The stockroom dashboard has a root counter, a substate counter and two independent ComponentState counters. Buttons populate2/3/2/1. A public `get_state` inspection event returns backend counts separately from visible text. Expiration cases use5seconds; a long ordinary event holds the state lock7seconds while a click queues, and a background event releases `async with self` during7seconds of simulated external work before reacquiring it.

A public registered lifespan task observes manager bookkeeping every200ms without get_state calls, loading state, changing deadlines, forcing GC or altering locks. It reads private lock/write-queue counts for measurement only, and writes a row on change or at least once per second. Browser correctness uses public Reflex APIs. These counts do not measure unreachable Python objects still awaiting GC.

The published default manager is **disk**. Memory is explicitly selected with `REFLEX_STATE_MANAGER_MODE=memory`. Both managers use **`REFLEX_REDIS_TOKEN_EXPIRATION`**, an integer number of seconds, not the guessed `REFLEX_STATE_EXPIRATION` in the brief. Every browser run asserts the resolved manager type, expiration and applicable debounce. Disk uses an explicit scratch `REFLEX_STATES_WORKDIR`; only file names/sizes/mtimes are archived, never pickles.

Runtime: Python3.12.14, Node26.8.1, actual managed Bun1.4.0, Playwright1.63.0. Browser versions are in results (Chromium153.0.8010.12 and Playwright WebKit). Frozen package graphs are in `environment/`; run JSON records imported Reflex paths, full distributions, commands and cwd. Python/app guards reject imports from the wrong environment. Source hashes are in `source-hashes.json`.

## Browser results and interpretation

`SUMMARY.json` derives **249 recorded checkpoints:245pass/4fail across23 browser executions**. The four failures are stable disk's retained-lock checks (dev Chromium, production Chromium/WebKit, and300-context churn). Two additional historical restart attempts aborted after seven passing setup checks each with a Playwright navigation error; these are incomplete, not passing cases. Corrected reruns completed. The background DOM anomalies are observations separate from the job-completion assertion counts.

| Workflow | Alpha2 | Stable0.9.12 |
| --- | --- | --- |
| Memory idle expiry, click, inspect, reload, ComponentState event |12/12pass |12/12pass |
| Disk idle expiry, new250ms / old0.25 setting |15/15pass in each alpha2 case |14/15pass, retained lock |
| Disk production expiry, Chromium and WebKit |15/15per engine |14/15per engine, retained lock |
| Held foreground event and released background job, memory/disk |10/10memory,12/12disk completion checks |Same |
| Backend worker reload preserves disk state, next event works |10/10pass |10/10pass |
| Full CLI restart resets disk state, next event works |10/10pass on corrected rerun |10/10pass on corrected rerun |

**Ordinary expiry:** after populated counters go idle beyondTTL, manager states reach0; disk files disappear. The next root click updates the entire visible tree to1/0/0/0, the server inspection agrees, reload remains correct, and a later idle+reload starts fresh with working component events. Stable memory also removes its lock; stable disk retains one lock per expired session. Alpha2 disk removes that lock. Both alpha2 debounce names give the same behavior.

**Held lock:** while the7second event holds the lock beyondTTL5, both versions/managers keep the lock and ultimately preserve the session: queued increment yields root13 with child3/components2/1. Stable disk temporarily reports cached states0 while the lock remains held; alpha2 keeps the active cached state. No user-visible loss occurs in this fixture.

**Released background task — stale browser view:** all four version/manager combinations complete the job after reacquiring fresh state. The backend inspection returns root10/child0/components0/0. Immediately after completion, however, the saved `after_job_visible` is root10/**child3/components2/1**. Reload corrects the old untouched values. This is a pre-existing browser-consistency weakness in this exact background-expiry path, not a claim that expired application state should be retained. Ordinary post-idle foreground events correctly refresh every displayed count. The full event frames, actual DOM snapshot and subsequent expected/actual backend check are preserved; `SUMMARY.json.background_visible_anomalies` makes the discrepancy explicit. Passing job-completion checks do not mean the entire DOM was consistent.

**Persistence boundary:** a benign source edit triggers a normal dev backend worker reload. The observer confirms a new worker PID; disk state survives and hydrates2/3/2/1, and the next child click yields4. In contrast, every full `reflex run` invokes `reset_disk_state_manager()` before starting (published `reflex/reflex.py:642` on alpha2), explicitly deleting disk states. Both versions reset to0/0/0/0 on full CLI restart, including when theTTL is120seconds. This boundary is important for users expecting persistence. The first two full-restart attempts used immediate Page.reload during automatic navigation and got `Not attached to an active page`; corrected attempts wait and navigate with bounded retry. Historical errors and logs remain unchanged, and no persistence claim comes from those aborted runs.

## 300-context observations

Each of four production runs warms one session, lets it expire, then creates300 independent Chromium contexts at bounded concurrency6. Every context clicks once, waits for root1/other0, records a unique token hash and closes. All1,200 test contexts succeed with300 unique tokens per run; four warm-up sessions also succeed. Only one server ran at a time, after other task servers stopped. RSS samples cover the backend worker PID only, not the browser, CLI parent or whole process tree.

| Run | RSS KiB before / sampled peak / after idle | State count before / peak / after | Lock count before / peak / after |
| --- | --- | --- | --- |
| Alpha2 memory |68352 /83312 /77184 |0 /100 /0 |0 /100 /0 |
| Stable memory |68368 /85104 /79696 |0 /100 /0 |0 /100 /0 |
| Alpha2 disk |68880 /85104 /79920 |0 /102 /0 |0 /102 /0 |
| Stable disk |68176 /86944 /82032 |0 /102 /0 |1 /301 /301 |

After-idle sampling occurs10seconds after the last context closes (TTL5+5seconds). Disk files are empty on both trains. Stable's301 locks are the warm-up plus300 test sessions; alpha2 returns to0. RSS falls from each observed peak but stays above its warmed baseline. Python/runtime allocator retention is not evidence of live-state leakage by itself. This single series per version/manager does not quantify the immediate object-release/GC improvement or prove a throughput/performance claim; sampling is1Hz and may miss a higher transient peak. Full metric and RSS series remain available.

## Durations, warnings and other anomalies

Eleven isolated configuration probes pass their recorded numerical/error expectations. New250ms and bare0.25 both resolve0.25seconds; zero resolves0; deprecated0.25 remains supported; new500ms wins when both names are present. abc and5x raise clear `EnvironmentVarValueError` naming the setting and accepted units. **The brief's -5s example is valid signed syntax:** it is accepted as-5seconds, and the published disk manager uses its <=0 immediate-write branch. This is recorded behavior, not a new invalid-input bug. Parsing/App construction was probed; no browser case for negative debounce was run.

Repeated direct and generated-code calls produce one deprecation warning per process, naming the real `duration_probe.py` line rather than `<string>`/frozen code. Four explicit checks are in `durations/warnings.json`. The old500ms auto-reload setting resolves0.5seconds. A full dev server log contains separate old-debounce warnings from compile and backend processes, each pointing to the real app source line. No two-edit automatic-error-reload timing test was run.

Normal browser expiry/job/churn runs have zero captured browser warnings/errors/failed HTTP requests. Full CLI restart records five connection-refused WebSocket errors while its backend is intentionally stopped; worker-reload runs have zero browser anomalies. Stable logs `CancelledError: lifespan_cleanup` for the ordinary observer coroutine when the server closes; alpha2 does not. Several Mac dev shutdowns log `[ERROR] Unexpected exit from worker-1` after explicit stopping/flush, with all checks already finished and final cleanup empty. All logs are retained; these are not silently classified as warning-free runs. Sitemap/implicit-Radix warnings are also preserved.

## Exact clean replay

```bash
QA_ARTIFACT=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/statemgr_perf/expiry
QA_SCRATCH=/private/tmp/reflex-expiry-rerun
bash "$QA_ARTIFACT/bootstrap.sh" "$QA_SCRATCH"
cd "$QA_SCRATCH"
export UV_CACHE_DIR="$QA_SCRATCH/uv-cache"
uv --no-config run --no-project --python "$QA_SCRATCH/envs/driver/bin/python" python "$QA_ARTIFACT/run_case.py" --sb "$QA_SCRATCH" --train alpha2 --manager disk --scenario expiry --port 3260 --backend-port 8260 --out "$QA_SCRATCH/results/statemgr_expiry" --attempt replay
```

The bootstrap uses only frozen PyPI distributions in fresh environments and installs matching Playwright browsers. It does not pin system Node or the managed Bun installation; those versions above are needed for exact runtime parity. The runner copies the fixture, records resolved config, starts the chosen published CLI, drives browsers and cleans its owned process group. Existing app/output paths are refused. All scenarios default toChromium; production smoke used `--browsers chromium,webkit`.

For each additional case, use a fresh attempt if its train/manager/scenario/name/mode already exists:

- Stable disk: `--train stable --manager disk --debounce-name old --debounce-value 0.25`; expected exit1 only for retained-lock checks.
- Memory: `--manager memory`; both trains expect exit0.
- Old-name alpha2 parity: `--debounce-name old --debounce-value 0.25`.
- Long jobs: `--scenario jobs --expiration 5`; server completion assertions expect exit0, inspect the separate `after_job_visible` anomaly.
- Worker persistence: `--scenario worker-reload --expiration 120 --mode dev`; it appends a benign comment only in the scratch app and records the new backendPID. Both trains expect preserved2/3/2/1.
- Full CLI reset: `--scenario restart --expiration 120 --mode dev`; both trains expect defaults after restart.
- Production expiry: `--mode prod --port 3262 --backend-port 3262 --browsers chromium,webkit`.
- Churn (run serially on a quiet machine): `--scenario churn --mode prod --port 3263 --backend-port 3263 --expiration 5 --contexts 300 --workers 6`. Repeat both trains and managers; stable disk expects exit1 for retained locks.

Duration probes and archive/summary commands:

```bash
uv --no-config run --no-project --python "$QA_SCRATCH/envs/driver/bin/python" python "$QA_ARTIFACT/run_duration_probes.py" --sb "$QA_SCRATCH" --out "$QA_SCRATCH/results/statemgr_expiry/durations"
uv --no-config run --no-project --python "$QA_SCRATCH/envs/driver/bin/python" python "$QA_ARTIFACT/archive_run.py" "$QA_SCRATCH/results/statemgr_expiry/alpha2-disk-expiry-new-dev-replay" "$QA_SCRATCH/archived/alpha2-disk-expiry-new-dev-replay"
```

`run_case.py` exit1 propagates browser failures/driver errors/cleanup failures. Shell loops used during this campaign print each runner's status and continue; their own final status must not replace per-run JSON. `summarize.py` regenerates SUMMARY from this artifact's archived runs. Ruff formatting and E9/F63/F7/F82 checks pass. Final owned groups/ports are recorded in `cleanup-final.json`; all contexts/browser processes are closed by finally blocks. Full gzip logs and browser records fit below3MB; churn frame sampling is limited to first/final two test contexts, while all300 event outcomes/token hashes are retained.
