# Nested order-state and computed-cache browser QA

Published 0.10.0a2 and 0.10.0a1 pass the dashboard's nested dataclass/list, dependency, background and session-isolation workflows. Nested dictionaries mutated through `.values()` or `.items()` stay stale in the browser on **all three trains**, including 0.9.12. This is pre-existing correctness behavior, not a 0.10 regression. An inherited-background mutation failure on stable is corrected in both alphas.

Owned scope: `browser_cache_bundle/state_cache/`, frontend ports 3720–3729 and backend ports 8720–8729; production uses the same assigned frontend port for both services. Parent separately owns deployment/default-hash/reconnect and external-data cache=False hydration. No framework changes, Git operations, shared-environment installs, or private state-manager overrides.

## Fixture and oracle

The app is an order/inventory dashboard. `Cart` holds nested dataclasses with list/dict default factories, stock dictionaries, a mutable default matrix, discounts and backend-only audit entries. Cached and cache=False values expose line data and subtotals. Cached dependencies extend through `Fulfillment(Cart)` and sibling `Review` using public `get_state`. Background events mutate inherited values under `async with self`.

The driver uses its own plain-Python dictionary oracle, importing neither the app nor Reflex. Each checkpoint compares 17 visible projections, including raw serialized values, computed values and foreach rows. Independent contexts A/B/C, full reloads and fresh-session controls use eight-second convergence windows (30 seconds on initial load). Failed checkpoints retain expected/actual differences. Later steps continue; propagated failures are not separate bugs.

Coverage: indexed aliases, normal/sorted/slice/list-copy iteration, nested dataclass attributes, `.asdict`/`.astuple`/`.replace`, append/pop/reverse/in-place sort/slice assignment, reads before and after cached writes, read-only operations, dict views/get/setdefault/update/keys, backend audit lists, discounts, inherited background events, sibling mutation, reset, reload, mutable default isolation and late new sessions. Hypotheses came from the runtime-hot-path, field-descriptor, state-var-type-check-depth and inherited-var-proxy news fragments.

## Results

| Train/mode | Engines | Checkpoints per engine | Pass | Fail |
| --- | --- | ---: | ---: | ---: |
| 0.10.0a2 dev, initial | Chromium | 39 | 37 | 2 |
| 0.9.12 dev | Chromium, WebKit | 39 | 31 | 8 |
| 0.10.0a1 dev | Chromium, WebKit | 49 | 43 | 6 |
| 0.10.0a2 dev, expanded | Chromium, WebKit | 49 | 43 | 6 |
| 0.10.0a2 prod | Chromium, WebKit | 49 | 43 | 6 |
| 0.9.12 prod | Chromium, WebKit | 49 | 37 | 12 |
| 0.10.0a1 prod | Chromium, WebKit | 49 | 43 | 6 |

Initial alpha2 dev and stable dev used 39 checkpoints. Later runs add ten isolated inventory/reload/control checkpoints to the same main workflow. `runs/*/run.json` and compressed browser results are authoritative. Runner exit 1 reflects recorded correctness failures, not startup failure. The production shell loop printed each runner status and continued; its own eventual exit status is not the per-case result.

**Inventory views:** tea10/mug20/total30, decrement each stock via `.values()` once, expect tea9/mug19/total28. Browser raw inventory and cached sum remain unchanged. `.items()` behaves identically. A fresh-session reload restores raw inventory to9/19 but leaves cached total30. Explicit field reassignment heals total28. Iterating keys and using indexed access updates all fields immediately. A subsequent tracked `.get()` mutation delivers accumulated preceding changes. Websocket excerpts show outgoing view-mutation events with no incoming event delta before the next operation; the tracked control sends new inventory and sum. Isolated reload behavior is confirmed on stable production and both alphas' dev/prod. See `CANDIDATE-inventory.md` and inbox draft.

**Inherited background:** stable finishes all three steps and updates uncached projections, but raw/cached parent lines, totals, invoice/quote, rows and cached audit entries remain stale. The next sibling mutation exposes line updates; audit entries stay stale through later steps and reload. These are one inherited-dirty-tracking path with downstream consequences, not six independent defects. Both alphas pass, consistent with the documented inherited-mutable-var fix.

**Passing controls:** all other listed mutations and synchronous dependency invalidation, in-event cached reads, cross-substate quote, reset and default/session isolation pass on all trains. No mutation leaked between browser contexts. This does not establish absence of defects outside these operations.

## Runtime, anomalies and evidence

macOS26.6.2 arm64, Python3.12.14, Node26.8.1, Playwright1.63.0. **Actual managed Bun1.4.0**, `/Users/masen/Library/Application Support/reflex/bun/bin/bun`, is confirmed in server system-info lines; PATH Bun1.3.14 is not used. `environment/*.txt` freezes all four read-only PyPI graphs. Each run records exact Reflex import path and installed distributions; guards reject the wrong environment.

Chromium has no captured browser anomalies. WebKit dev has unused modulepreload warnings for three React Router resources (browser-manifest, entry.client.js, root.jsx):9 in stable's shorter run and27 in each expanded alpha dev run. Assertions and event delivery continue. Both engines have zero browser anomalies in production. Stable logs nonfatal `Error transforming event payload` messages for `Cart.mutate`'s string argument; operations execute. These are retained observations, not new-train regression claims. Alpha1 dev logs one `[ERROR] Unexpected exit from worker-1` during explicit shutdown, after `Stopping worker-1` and the completed disk flush; all assertions finished beforehand and final group/ports are empty. It is retained as a shutdown anomaly, without a root-cause claim. Informational React/Vite lines and Bun peer-dependency warnings are retained too.

Full server logs, messages and websocket frames are gzip-compressed without entry filtering. Frame capture caps at4,000 per browser run; maximum observed was162. Total607 checkpoints:517pass,90fail across13 browser executions. Selected screenshots keep this allocation below2.2MB; full uncompressed JSON and extra screenshots remain in original `$SB/results/state_cache/`. JSON and event deltas distinguish browser staleness from backend mutation. No performance/RSS claims on the shared machine.

## Exact clean replay

Use a new neutral scratch directory. Bootstrap installs only frozen PyPI packages and pinned Playwright browsers, refuses existing named environments, and never installs from the checkout. Runtime parity additionally requires the Node and managed Bun versions above; bootstrap does not pin them.

```bash
QA_ARTIFACT=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/browser_cache_bundle/state_cache
QA_SCRATCH=/private/tmp/reflex-state-cache-rerun
bash "$QA_ARTIFACT/bootstrap.sh" "$QA_SCRATCH"
cd "$QA_SCRATCH"
export UV_CACHE_DIR="$QA_SCRATCH/uv-cache"
uv --no-config run --no-project --python "$QA_SCRATCH/envs/driver/bin/python" python "$QA_ARTIFACT/run_matrix.py" --sb "$QA_SCRATCH" --train alpha2 --mode dev --port 3720 --backend-port 8720 --out "$QA_SCRATCH/results/state_cache" --attempt replay
```

The runner copies exact app source into `$QA_SCRATCH/apps/state_cache/alpha2-dev-replay`, records packages, starts the matching published CLI there, drives Chromium/WebKit and performs bounded cleanup. Exit1 is expected for six inventory checkpoints per engine. For stable or alpha1 change `--train` to `stable` or `alpha`. Repeated train/mode runs need fresh `--attempt` values; existing app/output directories are refused.

Production uses the same command with `--mode prod --port 3723 --backend-port 3723`. A current complete matrix is six sequential invocations: `alpha2`, `stable`, `alpha`, each dev and prod. Do not use shell `set -e` across expected failures. `run_matrix.py` records the exact server subprocess command and app cwd. Python/Reflex subprocesses are children of the uv-selected driver and execute outside the checkout. Client HTTP bypasses proxies; server environment does not receive NO_PROXY.

Archive a fresh run without bulk screenshots:

```bash
uv --no-config run --no-project --python "$QA_SCRATCH/envs/driver/bin/python" python "$QA_ARTIFACT/archive_run.py" "$QA_SCRATCH/results/state_cache/alpha2-dev-replay" "$QA_SCRATCH/archived/alpha2-dev-replay"
```

Each run records process rows before cleanup, final empty owned group and listeners. Final allocation cleanup is saved separately after the matrix. Browser contexts/browser processes close in driver finally blocks. State expiration, deployment, Redis, enterprise and large-load behavior are outside this fixture.
