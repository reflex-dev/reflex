# Independent expiry verification — complete

Status: all four authorized dev runs completed after the performance campaign's
08:34:38 UTC cleanup gate on 2026-10-07. Published 0.9.12 and 0.10.0a2, memory and
disk storage, Chromium 153.0.8010.12 and WebKit 26.6 on macOS reproduced the same
partial refresh in all eight background cases. All eight ordinary idle controls
and all sixteen public-receipt/reload checks passed. This independently confirms
a **low-severity, pre-existing browser consistency issue**, with no alpha2 regression
demonstrated. No framework or Git changes are included; no timing claim is made.

Preparation started no app, browser, build, or server. Runtime remained behind
`EXPIRY_VERIFY_AUTHORIZED=1` until the coordinator authorized it. Each of the four
owned server groups and both reserved ports, 3266/8266, were clean after its run.

## Verified results

| Published version | Manager | Background cases with stale DOM | Idle controls correct | Receipt/reload checks correct |
| --- | --- | --- | --- | --- |
| 0.9.12 | memory | 2/2 | 2/2 | 4/4 |
| 0.10.0a2 | memory | 2/2 | 2/2 | 4/4 |
| 0.9.12 | disk | 2/2 | 2/2 | 4/4 |
| 0.10.0a2 | disk | 2/2 | 2/2 | 4/4 |

Each pair is Chromium and WebKit. In every background case, the completed job
showed root=100, child=11, left=13, right=17, including after the 200ms settling
period. The public server receipt showed root=100 and all three untouched counters
zero. The inspection event refreshed those visible counters, and reload retained
the corrected values. Every idle foreground recovery already showed root=1 and
all other counts zero **before** inspection.

All eight background websocket traces contain a completion delta with only the
root state's `processed_rx_state_=100` and `status_rx_state_="complete"`. They do
not contain child/component resets before inspection. The inspection event causes
full hydration with three zero child/component counters before its receipt delta.
Idle recovery sends full hydration and then the root increment. Outbound frames
show no intervening application event during background waiting or the settling
period. Stable uses separate initial hydrate/on-load events; alpha2's connection
handshake carries `hydrate_and_load`, as expected from its different wire protocol.

Across all sixteen contexts: zero console errors, page errors, HTTP errors, or
failed requests; none of the capture limits were reached. Each WebKit context had
three identical unused-modulepreload warnings (24 total), present in both versions.
Chromium had no warnings. All server logs were reviewed, including startup and
shutdown. Shared startup messages concern implicit Sitemap/Radix plugins and a
React peer dependency. The `dev` subprocess exit143 in all four runs, and
`Unexpected exit from worker-1` in stable/memory and alpha2/disk, occur during the
driver's deliberate process-group SIGTERM, after browser observations. These are
retained cleanup diagnostics; no application traceback was observed.

The first attempts completed without fixture or driver errors; there are no omitted
failed attempts. The original raw JSON, complete server logs, and all screenshots
remain under `results/`, about 1.22MB total. [report.json](report.json) is a structured
audit of the four runs, including exact completion deltas and diagnostic counts.
The final [cleanup audit](cleanup.json), at 08:43:21 UTC, found no members of the
four owned process groups and no listeners on either reserved port. It also
verified identical fixture source in every scratch app and successful syntax
checks. The entire verifier and evidence directory is about 1.29MB.
Representative screenshots are
[alpha2/WebKit before inspection](results/alpha2-memory-dev-1/webkit-background-before-inspection.png),
[alpha2/WebKit after reload](results/alpha2-memory-dev-1/webkit-background-after-reload.png), and
[stable/Chromium before inspection](results/stable-memory-dev-1/chromium-background-before-inspection.png).

## Independent hypothesis

The originating expiry report describes a background job that releases its state
lock while waiting longer than the configured session lifetime. When it completes,
the backend has a new session state, but its partial update may leave untouched
substate and ComponentState values from the old session visible in the browser.

The independent fixture was designed from that written description and the public
app source in `../expiry/app/`; the original browser driver was not read or copied.
The originating `expiry/NOTES.md` contained the TTL/environment description but no
exact driver invocation at preparation time. The commands below are complete
commands for this independently implemented verifier.

The new `ExportDesk` app initializes counters to root=7, child=11, left component=13,
right component=17 using an ordinary seed event and public `get_state` calls. The
external export sets status, releases the lock, waits 8 seconds, then reacquires
the state lock and adds 100 to the root counter. The configured session TTL is
5 seconds. **The shortened TTL simulates a long external export or import exceeding
the application's configured session timeout; it is not a proposed production TTL.**

Intentional expiration and partial browser refresh are separate questions. A reset
backend state after the TTL is expected. The candidate anomaly is a browser showing
old untouched values after it has accepted the completed job's new root value.

## Browser procedure and control

Each run creates four independent contexts: Chromium and WebKit, each with one
background-completion case and one ordinary-idle case. They have separate tokens.
The contexts may run concurrently, but only one app server runs at a time.

For the background case, the driver records four visible counts immediately when
completion becomes visible and again after 200 milliseconds without backend events.
This distinguishes a transient render step from a persistent partial refresh. It
saves the latter screenshot **before** clicking the server-inspection control.
An ordinary event then uses public `get_state` to produce a JSON receipt containing
root/child/both component counts; it does not mutate those counters. The driver
captures the receipt and DOM after this potentially corrective foreground event,
then reloads and verifies the same counts. Full websocket frames show exactly which
state values the server sent around completion, inspection, and reload.

The idle control starts from the same seeded values, waits 9 seconds without state
events, and clicks an ordinary foreground increment. It must converge to root=1
and all other counts=0, agree with the public receipt, and persist after reload.
Its pre-recovery DOM is retained: old values while the user is simply idle are not
the reported defect. The background backend expectation is root=100/others=0.

The verifier does not inspect manager internals, run GC, mock expiration, mutate
framework code, use Redis, or infer server values from frontend state. The app
prints its published import path/version and resolved public config; all Python
runs from neutral scratch with uv and environment-specific import guards.

## Interpretation and limits

- Both versions show stale untouched values after background completion while
  the public receipt and reload agree on zeroes: this is a pre-existing browser
  consistency issue. Intended TTL state loss is separate and is not a regression.
- Ordinary foreground recovery is correct across both engines and managers.
- A successful job followed by inconsistent visible filters/counters can mislead
  users of an export/import workflow. Releasing the lock during external I/O is a
  realistic pattern, and configured session timeouts can be shorter than that I/O.
  The default, much longer timeout makes the demonstrated trigger less common.
- Severity is low for this narrowly demonstrated session-expiry UI
  problem. Medium could be justified if follow-up shows meaningful downstream
  decisions or edits using the stale view. There is no evidence here of database
  corruption, cross-user leakage, or loss beyond configured session expiration,
  so a high-severity claim is not justified.

The simulation uses an asynchronous wait in place of external export/import I/O.
It demonstrates the state lifetime and partial-refresh behavior, not an actual
exported-file workflow or downstream decision failure. Medium severity would need
that additional evidence. This independent matrix covers dev memory/disk only;
production and Redis expiry were not run here. Observed elapsed times establish
ordering relative to TTL, not a performance comparison.

## Exact rerun commands

```sh
export SB=/private/tmp/reflex-prerelease-macos-pass2
export UV_CACHE_DIR="$SB/uv-cache"
export ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/statemgr_perf/verify_expiry
cd "$SB"
# Set this only after the coordinator explicitly authorizes this verifier.
export EXPIRY_VERIFY_AUTHORIZED=1
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env stable --manager memory
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha2 --manager memory
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env stable --manager disk
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" --sb "$SB" --env alpha2 --manager disk
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/audit.py"
```

Run sequentially. Each refuses an existing scratch directory; use `--attempt 2`
for a repeat. Optional `--mode prod` creates a distinct case directory and uses
3266 for both frontend and backend; dev uses 3266/8266. Changing `--ttl`/`--delay`
requires delay to exceed TTL by more than one second. Disk debounce is explicitly
250ms via the new alpha2 setting or stable's equivalent old 0.25 setting.
`audit.py` only reads the four primary `dev-1` result files and writes `report.json`;
it starts no app or browser. Use the compressed raw results directly for any reruns
with a different attempt suffix.

Evidence is `results/<env>-<manager>-<mode>-<attempt>/`: compressed full
JSON with console, page errors, requests, phase timestamps, and websocket frames;
small `summary.json`; screenshots before inspection and after reload; gzip server
logs; and process-group/port cleanup evidence. A background DOM mismatch is reported
explicitly as `visible_backend_mismatch` rather than turned into a hidden driver
failure. Nonzero exit indicates a harness, expiry expectation, idle-control,
persistence, uncaught browser error, or cleanup failure. Review the mismatch field
even when the verifier exits zero.
