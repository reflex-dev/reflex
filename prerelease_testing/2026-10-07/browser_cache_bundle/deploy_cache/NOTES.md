# Production deployment defaults, history and pure uncached values

Completed on macOS 26.6.2 arm64 using published `reflex` 0.9.12, 0.10.0a1 and 0.10.0a2; exact Python graphs in `evidence/*-freeze.txt`. Python 3.12.14, Playwright 1.63.0, Chromium 153.0.8010.12 and Playwright WebKit 26.6. Framework code was never imported from or installed from the checkout. App modules assert the selected published environment. Managed Bun 1.4.0, Node 26.8.1. No framework changes.

## Outcomes

There are 323 passing deployment assertions, six deliberately incompatible deployment journeys that fail hydration, and 40 passing pure-computed-value assertions. A failed journey is retained as an exception, not counted as a passing assertion. `summary.json` is generated from the raw JSON files by `summarize.py`.

| Exported frontend | Backend | Outcome in Chromium and WebKit |
|---|---|---|
| stable, revision A | stable A | All 19 checks pass |
| alpha1 A | alpha1 A | All 19 checks pass |
| alpha2 A | alpha2 A | All 19 checks pass |
| stable A | alpha2 A | All 19 checks pass; legacy hydrate path works |
| alpha1 A | alpha2 A | All 19 checks pass |
| alpha2 A | alpha2 B, same state names | All 19 checks pass; changed defaults and dictionary order arrive before the first user event |
| each train A | same train B plus new Billing state | All three trains fail hydration with a missing-dispatch diagnostic; pre-existing deployment mismatch |
| alpha2 B plus Billing | matching alpha2 B plus Billing | All 19 checks pass; matching rebuild resolves mismatch |

The realistic app is an account report dashboard. Revision B changes its plan, quota and feature insertion order. The frontend remains the previously exported revision A, served by a simple static server while `reflex run --env prod --backend-only` runs the selected published backend. A per-session UUID factory lives in a separate state so it cannot accidentally force full-state fallback for the deterministic account state. All app build paths contain spaces and `Café`.

Captured initial websocket frames confirm that matching alpha2 defaults omit the Account state, whereas changed backend defaults deliver the complete Account values (quota 250, Professional tier, reversed feature order). The changed-state-name case sends a full snapshot, but the old frontend has no dispatcher for Billing. It logs a clear developer diagnostic and does not hydrate; this is not a new optimization regression. Backend-only deployments that add states need matching frontend assets. The same-schema cross-version test preserves interactions, stored density preferences, state across reloads, independent factory IDs and separate browser contexts. It is not a Redis rollback test or a proof that arbitrary frontend/backend versions are compatible.

Actual external-document navigation is asserted before browser Back. All history returns and subsequent events pass. Neither engine restored a BFCache entry (`pageshow.persisted` was false). Removing Playwright's Chromium `--disable-back-forward-cache` default also produced ordinary history reloads on stable and alpha2; Chromium's subsequent `notRestoredReasons` was `masked`. **BFCache restoration remains unverified**; these runs establish history reload/reconnect behavior only. See `evidence/bfcache-attempt` and `history-reason`.

## N-016 control: a pure read-only uncached value

`uncached_probe.py` independently tests a warehouse page whose `@rx.var(cache=False)` reads a quantity from an external text store. The file is outside the watched app directory, so changing it does not restart the dev backend. The computed property performs no state writes. The sequence is: refresh at quantity 10; external sale sets 0; full reload displays 0; external restock sets 10; ordinary Refresh must display 10; final reload confirms 10. Every step passes in both engines on stable dev/prod, alpha2 dev/prod, and alpha1 dev (40 assertions).

This does **not** refute the coordinator's side-effectful N-016 reproduction. It limits its demonstrated scope: the equivalent pure externally supplied value does not become stuck in these tests. No high-severity read-only polling/data freshness regression is established by this control.

## Replay from a clean neutral directory

Choose a new scratch root. These commands install only exact PyPI graphs; they never install the checkout. Run cases sequentially and keep ports 3730/8730 and 3732/8732 free.

```sh
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/browser_cache_bundle/deploy_cache
export SB=/private/tmp/reflex-deploy-cache-replay
mkdir -p "$SB"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
for version in alpha2 alpha stable driver; do
  uv --no-config venv --python 3.12 "$SB/envs/$version"
  uv --no-config pip install --python "$SB/envs/$version/bin/python" --prerelease=allow -r "$ART/evidence/$version-freeze.txt"
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" playwright install chromium webkit
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run_matrix.py" "$SB" "$SB/results/deployment"
```

The default matrix intentionally includes three stale-schema cases and returns 1 for their recorded hydration failures. Matching rebuild control:

```sh
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run_matrix.py" "$SB" "$SB/results/matching" --cases alpha2-alpha2-B-extra --build-revision B --build-extra-state
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run_matrix.py" "$SB" "$SB/results/history" --cases alpha2-alpha2-A,stable-stable-A --bfcache --browsers chromium
```

Pure external inventory test (repeat with `--version stable --mode dev`, `stable/prod`, `alpha2/prod`, and `alpha/dev`):

```sh
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/uncached_probe.py" "$SB" "$SB/results/uncached" --version alpha2 --mode dev
```

Both harnesses refuse existing result directories; the uncached probe also refuses existing app directories. The deployment runner intentionally reuses a completed frontend export between backend variants. Source revision and build settings select its scratch app directory. All exact commands, source hashes, browser traces, console warnings/errors, HTTP failures, screenshots and complete gzip server/build logs are included. `run.json` records empty surviving process groups for every completed run; final reserved-port cleanup was empty.

Expected log noise: default SitemapPlugin notice, successful build peer-dependency/chunk warnings, and stable's event argument transformation warning followed by working events. Cross-version runs warn about the frontend/backend version mismatch. The new-state mismatch logs the captured dispatch error. No other browser/network errors occurred in successful deployment or pure-value cases.

An exploratory fixture was discarded before this matrix because its random factory shared the deterministic state and its help link stayed within SPA routing. It is described in the parent NOTES; its results are not used in counts or conclusions. The final explicit external help document and separate factory state prevent both blind spots.

Limits: memory state manager, one production backend worker, local static hosting, and a deliberately small state schema. No CDN behavior, true BFCache hit, distributed rolling deploy, rollback persistence, native Safari application, or native Intel macOS is claimed.
