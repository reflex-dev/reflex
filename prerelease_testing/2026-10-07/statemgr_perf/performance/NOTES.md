# Performance experiment preparation

Status: completed successfully on 2026-10-07, after the coordinator's explicit 08:26 UTC quiet-machine authorization. No other campaign Reflex/browser/Redis workloads were running; ordinary macOS applications remained open. Host metadata was captured at 08:28:29 UTC and final cleanup at 08:34:38 UTC. All 600 measured clicks, 60 warm-ups, semantic preflights, and repeated scalar/Var/compiler checks passed. No alpha2 median regression exceeded 20%. See `REPORT.md` and `comparison.json` for results.

The machine was an Apple M1 Pro MacBookPro18,3, ten physical/logical cores, 16 GiB RAM, macOS 26.6.2, Python 3.12.14, Chromium 153.0.8010.12 / Playwright 1.63.0, Node 26.8.1, and Bun 1.4.0. All measured runs were serial; each browser case restarted its server and browser context. `logs/host-at-quiet-authorization.json`, command records, and browser records retain load snapshots.

## Method

Same source on published PyPI `reflex==0.9.12` and `reflex==0.10.0a2`; exact environment freezes are in `logs/`. Imports assert that Reflex/Playwright came from the intended isolated environment. Python runs from neutral scratch paths using uv with project discovery disabled. The shared published environments are read-only. No repository-source import or installation is used.

- Ten separately named `rx.memo` functions derive 200 conditional/arithmetic Vars each (2,000 derived expressions), plus a foreach over a 200-item state list in each panel. A separate `/compile` route keeps this rendering workload out of event latency measurements.
- Three full production export repetitions per train after an unmeasured setup export. Version order alternates. Each command and browser run records host load averages before/after. Export logs retain package-install messages: stable may reinstall while alpha caches skip installation, so any total-export speedup must distinguish dependency install behavior from the separately reported Python compile phase. Complete subprocess wall time and Reflex's reported Python `Compile pages` phase are separate. Exports retain the scratch npm installation/cache: this is a warm-dependency export benchmark, not first-install cost.
- After initialization, three alternating `reflex compile --dry --no-rich --loglevel debug` runs measure the full Python compiler, including memo analysis/emission work before the dry-run return. Both the CLI internal `App compiled successfully` duration and complete process wall time are retained separately. `Compile pages` alone ends before memo emission and is not a full compiler measure. This does not isolate the memo-cache optimization from other Python compiler work.
- Production event app uses the memory manager. Each real button click sorts 5,000 dataclass rows by three attributes, sums units, and increments 50 state vars. Five warm-up clicks are excluded, followed by 50 measured clicks, repeated across three independently restarted server/browser contexts. An untimed zero-argument validation event invokes the same private workload helper with validation enabled, asserting its ordered keys are ascending and weighted identifier/rank checksum is 31,273,879,436. Validation runs outside the measured handler region and is disabled for all measured clicks. Expected units checksum is 2,497,500; every response must include all 50 correctly incremented fields.
- The handler records wall nanoseconds (`perf_counter_ns`) and process CPU nanoseconds (`process_time_ns`) only around sorting, summation, and the 50 mutations. These exclude socket handling, serialization, shared-state fan-out, and browser rendering.
- Before each measured browser context, a separate untimed context visits `/compile`, checks ten panels, and compares all 2,000 conditional expression values and 2,000 foreach values against independently calculated Python results. It also performs the sorting validation described above. These preflight sessions are discarded before the five warm-up clicks.
- Browser click-to-DOM timing starts at the native DOM click and ends at a MutationObserver on the sequence output. Websocket application-frame RTT uses Playwright callback timestamps from the outgoing event to the incoming state delta. Neither is a network-only measurement; neither includes Playwright's pre-click actionability wait.
- The same four cases run with/without an unused `rx.SharedState`, alternating version/configuration order each repetition. This app-level comparison can bound visible overhead but cannot isolate the tiny shared-state dispatch path from the much larger handler workload.
- Isolated direct scalar read/write probes use `StateManagerMemory.get_state(BaseStateToken(...))` then `root.get_state(StateClass)`. They do not bypass the prohibition on direct State instantiation. Three independent-process repeats of 100,000 reads and writes in each dev/prod environment, interleaved stable/alpha2 with reversed version order on the middle repetition, include Python loop and checksum arithmetic overhead. The counter resets to 2 before each timed read loop, and its checksum must equal 200,000 every repetition.
- Isolated Var construction repeats 2,000 dynamic expressions in three fresh processes, interleaved between release versions with reversed middle order. Outside the measured construction region, each generated expression is evaluated by Node with seed=7 and checked against an independent Python arithmetic/condition oracle. All samples are retained; this microbenchmark is not equated to complete application compilation.

No measurements ran concurrently with other campaign runtime workloads. A missed advertised speedup is an anomaly, not itself a functional defect. Any apparent slowdown requires checking repeated samples, phase boundaries, dependency differences, and source-generated workload before assigning severity.

## Exact setup and commands

Raw `.log` files preserve the CLI's original spacing, including trailing spaces. Source/document whitespace checks exclude these verbatim evidence files; the logs are not rewritten to satisfy source formatting rules.

Exact host-runtime parity additionally requires Node 26.8.1 and Reflex's managed Bun 1.4.0, with Bun selected rather than npm. Python freeze files do not pin those executables or the complete transitive npm graph. The measurements used retained warmed installations. Before treating a clean rerun as the same dependency graph, compare its generated package inventory with `frontend-dependency-inventory.json` and record any changed resolution; a fresh registry install may select newer compatible frontend dependencies. The original results remain comparisons of the recorded graphs, not a promise that today's unconstrained install is byte-identical.

The actual run reused read-only published environments under `/private/tmp/reflex-prerelease-macos-pass2`. For a fresh reproduction, choose a new scratch directory and install the exact saved freezes from PyPI; do not sync over the shared campaign environments. The commands below use the current checkout path as `EVIDENCE` and a new neutral scratch root.

```sh
export EVIDENCE=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/statemgr_perf/performance
export SB=/private/tmp/reflex-prerelease-performance-rerun
export REFLEX_TEST_SB="$SB"
export UV_CACHE_DIR="$SB/uv-cache"
export REFLEX_TELEMETRY_ENABLED=false
mkdir -p "$SB/envs" "$SB/apps/statemgr-performance"
cd "$SB"
for train in stable alpha2 driver; do
  uv --no-config venv --python 3.12.14 "$SB/envs/$train"
  uv --no-config pip sync --python "$SB/envs/$train/bin/python" --prerelease=allow "$EVIDENCE/logs/$train-freeze.txt"
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python -m playwright install chromium
cp -R "$EVIDENCE/source" "$EVIDENCE/scripts" "$SB/apps/statemgr-performance/"
cd "$SB/apps/statemgr-performance"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python scripts/run_suite.py --smoke --phase isolated
```

After coordinating that no other campaign runtime work is active and that port 8274 is free, run semantic preflights before collecting measurements:

```sh
export PERF_QUIET_CONFIRMED=1
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python scripts/run_suite.py --smoke --phase browser
cp runs/commands.json runs/commands-preflight-final.json
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python scripts/run_suite.py --phase all
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python scripts/summarize.py .
```

The archived run used these same commands, with the original scratch root. `--phase all` comprises eighteen isolated probe subprocesses, two setup exports, two setup dry compiles, twelve measured export/dry-compile subprocesses, and twelve measured browser-driver cases. Each browser case includes an untimed semantic preflight. The first historical preflight used a Boolean event argument, passed, and showed stable's pre-existing conversion warning. It is preserved as `*-smoke-initial*`; it is excluded from timing. All final-source preflights and measurements used zero-argument public events delegating to the same private workload helper, eliminating the warning.

`scripts/summarize.py` is read-only with respect to evidence except for writing `comparison.json`; it can be rerun against this artifact directory after copying the scripts there. The complete Python/npm package inventories, raw measured fixture/driver source archive, and SHA256 values are under `logs/`. The source archive preserves exact measured bytes even if a later readability-only formatter reflows the checked-in source.
Production frontend and backend both use the reserved port 8274, matching the API, readiness, and browser URLs. Both published CLI versions reject unequal production ports; `logs/production-port-source-check.log` records the source validation. Port 3274 remains unused. Only one server runs at a time. Client-only NO_PROXY/no_proxy overrides are stripped from server/export/probe environments and added only to the browser-driver child; HTTP readiness checks use httpx trust_env=False. Each server and its descendants are placed in a dedicated process group. Cleanup checks ps membership before SIGINT, SIGTERM, and SIGKILL, tolerates only a verified empty-group EPERM race, and requires no surviving group members at completion. Drivers return nonzero for semantic failure or browser/console/driver errors; orchestration continues the remaining independent cases and propagates child failure. All logs, full compressed websocket records, individual measurements, and essential screenshots belong under this directory; no `.web`, npm tree, environment, state database, or lockfile is an artifact.

Preparation review corrections were verified without benchmarks: inherited client bypass variables were absent from the generated server/export environment; a dedicated shell-plus-sleep process group required SIGTERM for its surviving child and then verified empty; a second cleanup call on that empty group passed. See `logs/harness-corrections-check.log`. The scalar read loop now resets to the same value before every repetition and asserts the same checksum.

Independent preparation review added complete Python compiler timing, exhaustive compile-route DOM semantics, validation of the actual sorted handler output, independent-process interleaving, and generated-expression JS evaluation. Published stable/alpha2 CLI support and memo timing boundaries are recorded in `logs/compiler-source-validation.log`. The updated six isolated smoke cases passed without collecting benchmark timings. Browser and full compiler preflights subsequently passed under the explicit quiet-machine authorization.

Browser observation coverage: the same helper is attached before navigation in preflight and measured/smoke pages. It retains console warnings/errors (with source location), pageerrors, failed requests (URL/method/type/failure), and HTTP 4xx/5xx responses. Non-cancellation errors invalidate the run. Warnings and explicit aborted/canceled request diagnostics remain separately classified for review; they do not automatically discard timings. Preflight websocket frames are also retained, outside measured samples. A synthetic callback check covered all four channels, confirmed ordinary errors fail while warnings/cancellations stay visible separately, and collected no browser timings (`logs/browser-observation-helper-check.json`).


## Evidence interpretation and review

`runs/*browser-[0-2].json.gz` contains all individual timing samples and raw application websocket payloads. `.summary.json` files retain the checks, diagnostic channels, three categories of latency/handler measurements, and sample counts. Repetition aggregation uses the median of the three 50-click run medians; full sample distributions remain available. `comparison.json` includes every repeat value and ratio. Empty diagnostic lists mean the shared observation helper saw no warnings/errors/cancellations, not that capture was disabled.

Screenshots show, in order below the buttons: validation flag, validation rank checksum, event sequence, units checksum, handler wall ns, handler CPU ns, first updated state var, and last updated state var. The timed context's first two values remain `false` and `0` because expensive validation runs in a separate discarded preflight context; the preflight checks record `true` and 31,273,879,436. The timed screenshot therefore is not a failed sorting check. A representative final alpha2 screenshot was visually inspected.

Adversarial review limits: (1) published dependency graphs differ, including wrapt and frontend tool versions; the report attributes results to those graphs. (2) Export's install/cache behavior is separated from Python compilation. (3) The heavy event does not isolate small unused-SharedState fan-out overhead, and full compilation does not isolate memo-body reuse. (4) An ordinary active macOS host is not an isolated lab; no throughput/concurrent-load or tail-latency claim is made. No unresolved semantic failure or >20% slowdown required further execution. No framework source, shared board, or Git state was modified by this worker.
