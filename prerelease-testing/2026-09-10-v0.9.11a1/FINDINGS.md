# Findings — reflex 0.9.11a1 pre-release testing (2026-09-10) — DRAFT, campaign in progress

Independent end-to-end exploration of the `r/pre-2026.09.10-34457666442` release train. All
installs PyPI-only in isolated uv venvs (never from a checkout); every sample app run for real
(`reflex run`, dev and prod) and driven in headless Chromium via Playwright with server-log /
console / network capture; claimed issues re-reproduced by independent adversarial verifier
agents from the written repro alone. Baselines against the previous stable, reflex 0.9.10.post2.

Campaign status: the orchestrated fan-out was interrupted twice by the organisation's monthly
spend limit (10:00 and ~14:30 UTC) and resumed from cache each time. This file is updated as
clusters complete; the per-cluster `NOTES.md` files are authoritative for detail.

## Versions under test (all published on PyPI, verified with check_release_versions.py)

reflex 0.9.11a1, reflex-base 0.9.11a1, reflex-components-radix 0.9.9a1, -code 0.9.5a1,
-moment 0.9.4a1, -plotly 0.9.6a1, -recharts 0.9.3a1, -sonner 0.9.3a1, reflex-hosting-cli
0.1.72a1, reflex-release 0.1.1a1, **reflex-otel 0.1.0a1 (new package)**. Unchanged in this
train: components-core 0.9.9, dataeditor 0.9.2, lucide 1.0.4, markdown 0.9.3, react-player 0.9.2,
docgen 0.9.5. Published reflex-enterprise: 0.9.5 (requires `reflex[db]>=0.9.6`).

Environment: Linux container, 4 CPU / 15 GB, Node v22.22.2, reflex-managed Bun 1.4.0 (system
bun 1.3.11 also present), Python 3.11.15 primary (3.10/3.12/3.13/3.14 via uv), Chromium via
Playwright, outbound via an egress proxy, redis-server available.

## Executive summary (interim)

What works: every headline changelog item exercised so far behaves as described — the hot-update
runtime fix (#7071) reproduces exactly the PR's verification table against a failing 0.9.10.post2
baseline; the Safari cache-bust streaming fix (#7048); the dev-server knobs (#7021); the whole
hybrid_property overhaul (#6812), dataclass proxy metadata (#7014) and ForwardRef probe guard
(#6929) including on Python 3.14; the background-flush-on-raise (#6995), redis post-eviction
rehydrate (#7072) and runaway-page-load fix (#7073), each with its bug reproduced on
0.9.10.post2; Bun 1.4 lockfile migration and the frontend pin bumps in place and cold; CLI
startup 0.66 s → 0.13 s (#7050). Ten reflex-examples apps... (pending: four done, see clusters).
Packaging: all 121 `.pyi` stubs ship correctly in wheel and sdist for all 17 packages.

What needs a decision or a fix before final:
- FINDING-001 (process): `reflex-otel 0.1.0a1` failed to publish from the release run (PyPI
  trusted publisher not configured for the new project); published manually 17 min later.
- FINDING-002 (regression, downstream, low): `rx.moment` `on_change` fires at mount under
  react-moment 2.0.2 — documented upstream as breaking, filed in our changelog as a bug fix.
- FINDING-003 (pre-existing, high): prod multi-worker + redis drops every cross-worker delta
  (all granian workers share one `RedisTokenManager.instance_id`). Not new, but the #7073
  hydrate delta is one of the things it swallows.
- Several verifier verdicts still pending (hybrid_property typing claim; bg_rehydrate items).

Index (confirmed = independently re-reproduced by a verifier; claimed = verification pending):
- FINDING-001: reflex-otel 0.1.0a1 not published by the release run (PROCESS, resolved)
- FINDING-002: rx.moment on_change fires at mount with react-moment 2.0.2 (LOW, regression, downstream) — CONFIRMED
- FINDING-003: prod multi-worker + redis: cross-worker deltas silently dropped, swallowing the new #7073 hydrate (HIGH, pre-existing) — claimed
- FINDING-004: client-storage vars show defaults after a backend rehydrate until a full reload (MEDIUM, pre-existing) — claimed
- FINDING-005: hybrid_property class-level typing works on the repo-pinned pyright 1.1.411 but degrades to `Any` from pyright 1.1.412 onward (MEDIUM, forward-compat) — CONFIRMED by version bracketing
- FINDING-006: uv cannot build the `reflex` sdist (workspace sources in pyproject) (LOW, pre-existing)
- FINDING-007: reflex-only in-place upgrade leaves the alpha sub-packages at their stable versions (LOW, upgrade-path note)
- FINDING-008: `reflex run --backend-only` leaks `.web/nocompile`; the next full run serves a stale frontend (MEDIUM, pre-existing) — claimed
- FINDING-009: `frontend_path` mis-routes pages whose route starts with the prefix text (MEDIUM, pre-existing) — claimed
- FINDING-010: a backend var named `_get_was_touched` breaks the disk state manager's persistence (MEDIUM, pre-existing) — claimed
- FINDING-011: state attribute names colliding with BaseState internals are unvalidated; some crash with `'int' object is not callable` (LOW, pre-existing) — claimed
- FINDING-012: `rx.Model(table=True)` without sqlmodel still gives a bare TypeError, no `reflex[db]` pointer (LOW, pre-existing, previous campaign's FINDING-014)
- FINDING-013: AttributeError inside a cached var computation is still masked as `Attribute _cached_get_all_var_data not found` (MEDIUM, pre-existing, previous campaign's FINDING-024)
- FINDING-014: `frontend_path` validation accepts segments Win32 trims (trailing space or dot) and empty segments (LOW, gap in #7044)
- FINDING-015: `reflex cloud regions/vmtypes --json` exit 0 with `[]` after a 403 (LOW, pre-existing, agent-usability gap)
- FINDING-016: `reflex run --json` stdout still carries 9 plain-text granian lines, breaking strict JSON-lines parsing (LOW, pre-existing, previous campaign's FINDING-013)

## FINDING-001: reflex-otel 0.1.0a1 not published by the release run (PROCESS, resolved)

- Cluster: `packaging` | Regression: n/a | Verifier: orchestrator (GitHub Actions evidence)
- Repro: at 09:01 UTC `check_release_versions.py --ref origin/r/pre-2026.09.10-34457666442`
  reported `reflex-otel 0.1.0a1 NOT ON PYPI`; run 34457698833 ("Release from changelog") job
  `publish (reflex-otel, 0.1.0a1)` failed at `uv publish` with
  `400 Non-user identities cannot create new projects ... pending publisher ... project name`.
- Evidence: `packaging/NOTES.md`; GitHub job 102808226580 log; the package appeared on PyPI at
  09:10 UTC and the discovery script passes since.
- Root cause: first release of a new distribution through trusted publishing without a matching
  pending publisher on PyPI. Action: make the pending-publisher step part of the new-package
  checklist so the next new package does not repeat it.

## FINDING-002: rx.moment on_change fires at mount with react-moment 2.0.2 (LOW, regression, downstream)

- Cluster: `up_counter_todo_clock` | Regression vs 0.9.10.post2: **yes** | Downstream:
  reflex-components-moment 0.9.4a1 | Verifier: CONFIRMED ("broader than claimed")
- Repro: venv with `reflex==0.9.11a1 reflex-components-moment==0.9.4a1`; any page with
  `rx.moment(interval=3000, on_change=State.on_update)` (also static dates and `interval=0`);
  load the page: `on_update` is called at mount — twice in dev (StrictMode), once in prod, and
  again on every remount (hard reload, client-side route remount). 0.9.10.post2 / react-moment
  1.2.2 never fires at mount. Automated: `up_counter_todo_clock/verification/` (`drive_moment.py`).
- Evidence: `up_counter_todo_clock/logs/linkinbio-0911-fulltrain-dev-verify-report.json`,
  `logs/server/linkinbio_run_0911_fulltrain_dev_verify.log`, verification appendix in NOTES.md.
- Root cause (verifier): react-moment 2.0.2 `useMomentUpdate` has an unconditional
  `useEffect(() => onChange(...), [])`; upstream MIGRATION.md lists "onChange fires on mount" as
  a breaking change. `moment.py:34` pins `react-moment@2.0.2` (#7006); the 0.9.4a1 changelog
  files the migration under Bug Fixes with no behaviour note; `docs/library/data-display/moment.md`
  still describes 1.2.2 semantics ("Fires when the date changes").
- Decision for maintainers: document it (changelog "Breaking"/behaviour note + docs) or restore
  the old semantics with a guard in the wrapper.

## FINDING-006: uv cannot build the `reflex` sdist (LOW, pre-existing)

- Cluster: `packaging` | Regression: no (identical on 0.9.10.post2)
- Repro: `uv pip install --no-binary reflex 'reflex==0.9.11a1'` →
  "`reflex-base` references a workspace in `tool.uv.sources` ... but is not a workspace member".
  The sdist ships the monorepo root pyproject.toml including `[tool.uv.sources]` and
  `[tool.uv.workspace]`. `pip install --no-binary` builds it fine (33 s); reflex-base's sdist
  builds under uv.
- Evidence: `packaging/logs/sdist_install.log`, `sdist_install_0910.log`, `sdist_install_pip.log`.

## FINDING-007: reflex-only upgrade leaves alpha sub-packages at stable (LOW, upgrade-path note)

- Cluster: `up_counter_todo_clock` | Regression: no
- `uv pip install --prerelease=allow 'reflex==0.9.11a1'` into a 0.9.10.post2 venv upgrades only
  reflex and reflex-base; radix/code/moment/plotly/recharts/sonner/hosting-cli stay at their
  stable versions because reflex pins them with `>=` and they already satisfy the constraint.
  Users testing the alpha therefore do not get the alpha sub-packages (and not FINDING-002)
  unless they pin them explicitly. Expected resolver behaviour; worth a line in the pre-release
  announcement.

## FINDING-005: hybrid_property class-level typing degrades to `Any` on pyright 1.1.412+ (MEDIUM)

- Cluster: `hybrid_property` (reported) / `orch_probes` (bracketed) | Regression vs 0.9.10.post2: no
  (0.9.10.post2 typed it as the descriptor) | Verifier: version-bracketed A/B with one identical file
- The reflex-base 0.9.11a1 changelog promises that "type checkers now resolve class-level access to
  the frontend var's type instead of the descriptor". That holds exactly at **pyright 1.1.411**, the
  version this repo pins (raised from 1.1.408 in this same train): `State.full` → `StringVar[str]`,
  `State.doubled` → `NumberVar[int]`, `State.positive` → `BooleanVar`, a var function with its own
  declared type → that type, instance access → the Python type. On 0.9.10.post2 the same file typed
  every one as `HybridProperty`, so the feature is a real improvement.
- From **pyright 1.1.412 onward** (412, 413 and 414 all checked) every class-level access types as
  `Any`. No error is raised, so downstream users on a current pyright silently lose the checking the
  changelog advertises. Instance access is unaffected.
- Repro and the full table: `orch_probes/NOTES.md` and `orch_probes/hp_types.py`.
- Maintainer decision: the overload set in `hybrid_property` needs to survive pyright's newer
  overload resolution, or the promise needs qualifying with a supported checker version.

## FINDING-008: `reflex run --backend-only` leaks `.web/nocompile`; the next full run serves a stale frontend (MEDIUM, pre-existing)

- Cluster: `event_hotpath` | Regression vs 0.9.10.post2: no (identical) | Verifier: pending
- Repro: in any app dir, `reflex run --backend-only --backend-port <BP>`, wait for `/ping`, stop it →
  `.web/nocompile` exists. Delete a compiled page (or edit the app to add a component), then run a
  normal `reflex run`: the marker is consumed, the log has no "Compiling" line, the page is not
  regenerated, and Vite exits with `ENOENT ... .web/app/routes/[...]._index.jsx` (or the browser
  silently shows the old UI).
- Evidence: `event_hotpath/logs/repro_nocompile_smoke.out`, `repro_nocompile_base0910.out`,
  `nocompile_smoke_fullrun.trimmed.log`.
- Why it matters here: it silently invalidated the first pass of this cluster's own browser runs,
  which is exactly how it would bite a user who runs the backend alone once.

## FINDING-009: `frontend_path` mis-routes pages whose route starts with the prefix text (MEDIUM, pre-existing)

- Cluster: `event_hotpath` | Regression: no (identical on 0.9.10.post2) | Verifier: pending
- Repro: `rx.Config(frontend_path='/app')` with pages `/apple`, `/app`, `/item/[id]`, `/docs/[[...splat]]`;
  open `http://localhost:<FP>/app/apple` (or click its link): the recorded `on_load` shows
  `path=/404`, `route_id=/404`; `/app/app` resolves to `/index` and fires the index page's on_load.
  Other prefixed routes match correctly.
- Root cause (reporter): the client sends the basename-relative pathname (`/apple`), and
  `route.get_route` strips `config.frontend_path` again with `str.removeprefix`, leaving `le`.
  #7025 memoized this matcher without changing the prefix logic.
- Evidence: `event_hotpath/logs/pw_routes_smoke_dev_fp/results.json` vs `pw_routes_base_dev_fp/results.json`.

## FINDING-010: a backend var named `_get_was_touched` breaks the disk state manager (MEDIUM, pre-existing)

- Cluster: `event_hotpath` | Regression: no | Verifier: pending
- Repro: add `_get_was_touched: int = 7` to a state, run with the default disk state manager, send one
  event, wait past the flush debounce: every flush logs `Error processing write queue:
  TypeError("'int' object is not callable")` and shutdown ends in a traceback from
  `istate/manager/token.py get_and_reset_touched_state`. State is never persisted. Reads and writes of
  the var in the browser work, so the failure is invisible from the UI.
- Note: #7025's own unit test uses this exact name as a supported collision, while the runtime call
  site (which predates the PR) calls it as a method.
- Evidence: `event_hotpath/logs/gwt_disk_smoke.trimmed.log`, `gwt_disk_base0910.trimmed.log`.

## FINDING-011: state attribute names colliding with BaseState internals are unvalidated (LOW, pre-existing)

- Cluster: `event_hotpath` | Regression: no (91/95 sweep outcomes byte-identical to 0.9.10.post2) | Verifier: pending
- Repro: `class S(rx.State): get_delta: int = 0` with a handler that increments it. Clicking does
  nothing; the server log shows `[Reflex Backend Exception] ... in get_delta:
  delta.update(substates[substate].get_delta()) TypeError: 'int' object is not callable`.
  The offline sweep (`event_hotpath/scripts/probe_names.py`) covers 19 framework names × 5 kinds:
  only a few collisions produce a clear error; `get_delta`, `get_value`, `_expired_computed_vars`
  and `_mark_dirty` crash the framework instead.

## FINDING-012: `rx.Model(table=True)` without sqlmodel still gives a bare TypeError (LOW, pre-existing)

- Cluster: `orch_probes` | Regression: no | This is the previous campaign's FINDING-014, still open.
- Repro (bare venv, no sqlmodel): `class Thing(rx.Model, table=True): name: str` →
  `TypeError: Thing.__init_subclass__() takes no keyword arguments`, with no mention of
  `reflex[db]` or sqlmodel. Evidence: `orch_probes/logs/probe_smoke.json`.

## FINDING-013: AttributeError inside a cached var computation is still masked (MEDIUM, pre-existing)

- Cluster: `orch_probes` | Regression: no (identical on 0.9.10.post2) | Previous campaign's FINDING-024.
- Repro: a `CachedVarOperation` subclass whose `_cached_get_all_var_data` raises `AttributeError`
  surfaces as `VarAttributeError: Attribute _cached_get_all_var_data not found.` with
  `__cause__` and `__context__` both unset — the real error is invisible.
  Run `orch_probes/probe_reverify.py` with any venv's python from `/tmp`.
- Why it still matters: this is what turned the previous release's headline enterprise breakage into
  an undebuggable message.

## FINDING-014: `frontend_path` validation accepts segments Win32 trims (LOW, gap in #7044)

- Cluster: `orch_probes` | Regression: no (the validation is new in this train, so this is a gap in a
  new guard rather than a break)
- The new validator (`packages/reflex-base/src/reflex_base/config.py:612`) correctly rejects `..`,
  `.`, backslashes and drive letters, naming the offending segment. It still accepts `/a ` (trailing
  space), `/ .`, `//srv` and `/a//b` (empty segments). Trailing spaces and dots are the same Win32
  trimming class the PR cites as its reason for rejecting drive letters and backslashes.
- Evidence: `orch_probes/logs/probe_smoke.json` (`frontend_path_validation`).

## FINDING-015: `reflex cloud regions|vmtypes --json` exit 0 with an empty list after a 403 (LOW, pre-existing)

- Cluster: `orch_probes` | Regression: no (identical on 0.9.10.post2)
- Repro: with no cloud token, `reflex cloud regions --json` prints `[]` to stdout and exits **0**
  while stderr says `Unable to get regions due to 403 Forbidden.`; same for `vmtypes`.
  `reflex cloud config --json` exits 0 with `{"generated": false, "path": null}` while stderr reports
  that PyYAML is missing (PyYAML is not a dependency of reflex-hosting-cli).
- Why it matters for this train: #6917's stated goal is an agent-usable CLI, and an agent that trusts
  the exit code reads an auth failure as "no regions exist". `reflex cloud project selected --json`
  already models the fix with an explicit `"error"` field.
- Evidence: `orch_probes/logs/cloud_sweep_0911.json`, `orch_probes/NOTES.md`.

(Findings 003–005 carry full detail in their clusters' NOTES.md; remaining clusters are appended as they finish.)

## FINDING-016: `reflex run --json` stdout is not strict JSON-lines (LOW, pre-existing)

- Cluster: `orch_probes` | Regression vs 0.9.10.post2: no (9 non-JSON lines on both) | Previous
  campaign's FINDING-013, still open.
- Repro: `reflex run --backend-only --json --loglevel debug --backend-port 8055 > out 2> err`, wait
  for `/ping`, stop it, then `json.loads` every non-empty line of `out`: nine granian lifecycle lines
  (`[INFO] Starting granian ...` through `Granian shutdown completed, see ya!`) are plain text among
  the JSON records, and stderr is empty.
- Contrast: `reflex cloud --json` is clean in this same train thanks to #6917's `reserve_stdout`;
  `reflex run --json` has not had the same treatment.
- Evidence: `orch_probes/logs/json_backend_0911a1.out`, `orch_probes/logs/json_backend_0910.out`.

## Cluster summaries (interim)

### `smoke` (orchestrator) — clean
Blank template on 0.9.11a1, dev and prod: 0 console/page/network errors; Bun 1.4.0 installed,
lockfile v2, `context.jsx` present, pins as announced.

### `packaging` (orchestrator) — pass, 2 notes
121 stubs OK across 17 packages; FINDING-001 (process) and FINDING-006 (pre-existing sdist).

### `hmr_runtime` (pass 25, anomaly 6, fail 0) — no 0.9.11a1 defect
PR #7071's verification table reproduced (0.9.10.post2 crashes with `Cannot read properties of
null` in the held-context step; 0.9.11a1 does not; 0 state.js refetches; 1 socket connection per
compile; client_state survives). Safari plugin: real HTML with a Safari UA, multibyte intact;
0.9.10.post1 reproduces the comma-separated-bytes body. Knobs behave as documented. Six
low-severity pre-existing anomalies (stale `__pycache__` on same-second double save; Vite
"Could not Fast Refresh" for context.jsx; duplicate HMR frames; bun install re-run per reload;
background task killed by worker restart; one extra reload when toggling the prod-React knob).

### `hybrid_property` (pass 27, anomaly 7, fail 1) — feature works; typing claim disputed
Dev 103/103, prod 103/103, Python 3.14 105/105 browser checks; every runtime claim of #6812,
#7014, #6929 verified with its bug reproduced on 0.9.10.post2. The one FAIL: pyright 1.1.413
resolves class-level `State.prop` to `Any` (1.1.389 gives the promised `StringVar[str]` etc.);
verification pending. Four low error-quality anomalies (None var fn silently renders nothing /
bakes "None" into f-strings; list/dict getters yield plain containers at class level; a
TYPE_CHECKING-only annotation on a dataclass hides all its attributes; `len(var)` raw TypeError).

### `bg_rehydrate` (pass 22, anomaly 5, fail 2) — fixes verified; adjacent pre-existing issues
#6995/#7072/#7073 all verified end-to-end (redis, memory, disk, prod) with each bug reproduced on
0.9.10.post2 (0.9.10.post2 spun the index loader ~220×/s on a backend-initiated event). FAILs are
the pre-existing prod multi-worker + redis delta drop (FINDING-003, claimed high) — verification
pending.

### `event_hotpath` (pass 32, anomaly 6, fail 2) — no regression from #7025
Event ordering, background tasks and StateProxy, 3-deep substates, interval computed vars, route
matching over 150+ routes, slow-handler isolation and a 100-click hammer all behave identically to
0.9.10.post2 on Python 3.11 and 3.13, with and without a custom asyncio task factory. Measured A/B
over the wire: +17% (3.11) / +21% (3.13) events/s at 20 concurrent clients and 14-16% less worker CPU
per event, all counters exact. The two FAILs and several anomalies are pre-existing (FINDING-008 to
FINDING-011).

### `up_upload_traversal_quiz` (pass 10, anomaly 4) — no regressions
upload, traversal and quiz upgrade cleanly (baseline, in-place, cold); sonner 2.0.8 toasts and shiki
4.4.3 highlighting render identically to their prior versions. Anomalies are app-level or pre-existing,
including `rx._x.code_block(use_transformers=True)` compiling `transformers:[]` so the shiki
notation comments are never applied (identical on 0.9.10.post2).

### `orch_probes` (orchestrator) — 2 fixed items confirmed, 4 pre-existing gaps
AppHarness now names `reflex[testing]` in its error (previous FINDING-016 fixed); `reflex_base.otel`
is genuinely inert without reflex-otel; all 34 `reflex cloud` leaf commands return off a TTY with
clean single-document JSON on stdout. Gaps: FINDING-012 to FINDING-015.

### `up_counter_todo_clock` (pass 18, anomaly 8, skipped 1) — no regression except FINDING-002
counter, todo, clock, linkinbio: baseline → in-place → cold identical (md5-identical screenshots),
Bun 1.3.11→1.4.0 migration clean, lockfile stays v1, `context.js` removed, package.json diff is
exactly the announced pins.
