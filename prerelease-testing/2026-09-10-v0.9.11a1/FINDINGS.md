# Findings — reflex 0.9.11a1 pre-release testing (2026-09-10)

Independent end-to-end exploration of the `r/pre-2026.09.10-34457666442` release train. All
installs PyPI-only in isolated uv venvs (never from a checkout); every sample app run for real
(`reflex run`, dev and prod) and driven in headless Chromium via Playwright with server-log /
console / network capture; claimed issues re-reproduced by independent adversarial verifier
agents from the written repro alone. Baselines against the previous stable, reflex 0.9.10.post2.

Campaign status: complete. Every claim in the 0.9.11a1 changelog has been exercised and every
reflex-enterprise demo has been run on both reflex versions. The orchestrated fan-out was
interrupted repeatedly by the organisation's monthly spend limit and was resumed from cache each
time; the later clusters were run in the foreground instead. The per-cluster `NOTES.md` files are
authoritative for detail.

## Versions under test (all published on PyPI, verified with check_release_versions.py)

reflex 0.9.11a1, reflex-base 0.9.11a1, reflex-components-radix 0.9.9a1, -code 0.9.5a1,
-moment 0.9.4a1, -plotly 0.9.6a1, -recharts 0.9.3a1, -sonner 0.9.3a1, reflex-hosting-cli
0.1.72a1, reflex-release 0.1.1a1, **reflex-otel 0.1.0a1 (new package)**. Unchanged in this
train: components-core 0.9.9, dataeditor 0.9.2, lucide 1.0.4, markdown 0.9.3, react-player 0.9.2,
docgen 0.9.5. Published reflex-enterprise: 0.9.5 (requires `reflex[db]>=0.9.6`).

Environment: Linux container, 4 CPU / 15 GB, Node v22.22.2, reflex-managed Bun 1.4.0 (system
bun 1.3.11 also present), Python 3.11.15 primary (3.10/3.12/3.13/3.14 via uv), Chromium via
Playwright, outbound via an egress proxy, redis-server available.

## Executive summary

Verified changelog claims (not findings): `reflex[testing]` + `AppHarness` runs an app end to end
(4/4 pytest checks) while a bare install raises an `ImportError` naming the extra (#6974/#7008);
`hybrid_property` class-level typing resolves to the frontend var type on the repo-pinned pyright
(#6812, see FINDING-005 for the newer-pyright caveat); `reflex_base.otel` imports nothing from
opentelemetry until the instrumentor is installed (#6227).

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
- FINDING-033 (regression, downstream, medium, CONFIRMED): with `reflex-components-moment` 0.9.4a1
  a `locale=` on one `rx.moment` changes the language of every other moment on the page, in dev and
  prod. Bisected to the component bump alone. **The one item worth holding the train for**; see
  RELEASE_PLAN.md.
- FINDING-001 (process): `reflex-otel 0.1.0a1` failed to publish from the release run (PyPI
  trusted publisher not configured for the new project); published manually 17 min later.
- FINDING-002 (regression, downstream, low): `rx.moment` `on_change` fires at mount under
  react-moment 2.0.2 — documented upstream as breaking, filed in our changelog as a bug fix.
- FINDING-003 (pre-existing, high, CONFIRMED): prod with redis and the default worker count drops
  backend-initiated deltas, because every forked granian worker shares one
  `RedisTokenManager.instance_id`. Measured: 4/6 delivered on 0.9.11a1 with 9 workers, 6/6 with one
  worker, 0/6 on 0.9.10.post2 with 8 workers. Not new, but it swallows the #7073 hydrate this train
  adds.
Later clusters added: enterprise MCP and OIDC driven end to end against a purpose-built OIDC
provider, the remaining enterprise demos, three reflex-examples apps upgraded in place, the six
component-library bumps in dev and prod, `frontend_path` + `REFLEX_SSR=false` (#7044), shared-asset
linking (#7039), CLI startup (#7050), the telemetry context fix (#6960) and the memoization naming
caches (#6947). All but the moment bump came back clean or pre-existing.

Index (confirmed = independently re-reproduced by a verifier; claimed = verification pending).
Findings 030-037 were found in the foreground clusters that closed the campaign:
FINDING-030 delta key ordering changed (LOW, new); FINDING-031 and FINDING-032 enterprise MCP
resource quirks (LOW, pre-existing); **FINDING-033 the `rx.moment` locale leak (MEDIUM, regression)
— CONFIRMED**; FINDING-034 seven component-library rough edges (LOW, pre-existing); FINDING-035 the
enterprise OpenAPI document 500s without `pyyaml` (LOW, pre-existing); FINDING-036 a delta sent for
substates the page has no dispatcher for (LOW, pre-existing); FINDING-037 `REFLEX_SSR=false` serves
every prod route but `/` as 404 (LOW, pre-existing).
- FINDING-001: reflex-otel 0.1.0a1 not published by the release run (PROCESS, resolved)
- FINDING-002: rx.moment on_change fires at mount with react-moment 2.0.2 (LOW, regression, downstream) — CONFIRMED
- FINDING-003: prod multi-worker + redis: cross-worker deltas silently dropped, swallowing the new #7073 hydrate (HIGH, pre-existing) — CONFIRMED (orchestrator; single-worker control delivers 6/6)
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
- FINDING-017: `rx.plotly` still emits `id` rather than `divId`, so the id never reaches the DOM, unchanged by the react-plotly.js 4.1.0 bump (LOW, pre-existing, previous campaign's FINDING-020)
- FINDING-018: dev mode: one unserializable state var drops the ENTIRE hydrate delta on every page load, silently reverting session state and showing a raw internal ValueError to the user (HIGH, pre-existing, triggered downstream) — claimed
- FINDING-027: reflex-otel's documented env-var setup exports nothing and logs a traceback twice, because the recipe's exporter package does not match the protocol `OTEL_TRACES_EXPORTER=otlp` resolves to (MEDIUM, new feature, trivially small) — the first thing a user of the new package will copy
- FINDING-028: the initial `reflex.compile` span tree is never exported in dev, lost with the compile worker (LOW, new feature)
- FINDING-029: installing reflex-otel next to reflex 0.9.10.post2 silently upgrades reflex-base and leaves an inconsistent environment (LOW, new package metadata)
- FINDING-026: `add_custom_code` JS touching `window` fails `reflex export` with an opaque prerender 500 that never names the offending code (LOW, pre-existing)
- FINDING-025: `rx.AdminDash` serves HTTP 500 on every `/admin` route on both versions and both starlette-admin generations, so this train's AdminDash changelog line is not observable end to end (MEDIUM-HIGH impact, pre-existing) — isolated against a plain Starlette app
- FINDING-022: `bundle_library()` at app-module scope is discarded before pages are evaluated, and the error tells you to do what you already did (MEDIUM, pre-existing) — seen independently by three clusters
- FINDING-023: a hook-bearing component used directly inside `rx.foreach` compiles silently, then throws `ReferenceError` and blanks the page (MEDIUM, pre-existing)
- FINDING-024: reflex's own error boundary logs three React "Invalid DOM property" errors every time it renders (LOW, pre-existing)
- FINDING-021: a single `REFLEX_USE_NPM=1` run converts a project to npm permanently and silently (LOW, pre-existing); the previous campaign's FINDING-018 did NOT reproduce
- FINDING-019: four shipped reflex-enterprise 0.9.5 defects that block its own demos (stale bundle path, ModelWrapper URL encoding, ag-grid/ag-charts version mismatch, `column_def()` dropping unknown kwargs) (MEDIUM, pre-existing, downstream)

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

## FINDING-003: prod multi-worker with redis drops backend-initiated deltas (HIGH, pre-existing, CONFIRMED)

- Cluster: `bg_rehydrate` | Regression vs 0.9.10.post2: no (the baseline is worse) | Verifier:
  orchestrator, from the written repro in a fresh directory
- Every forked granian worker reports the same `RedisTokenManager.instance_id` (9 distinct pids,
  1 id), because `_run_prod` imports and compiles the app — constructing the token manager — before
  granian forks. `RedisTokenManager._fetch_socket_record` on a non-owner worker sees
  `record.instance_id == self.instance_id` with an unknown sid, treats it as its own stale socket,
  and returns None, so `emit_update` drops the delta instead of publishing it to the owner.
- Measured with one driver over six backend-enqueued events into a live page:

| version | workers | deltas delivered |
|---|---|---|
| 0.9.11a1 | 9 (default) | 4 / 6 |
| 0.9.11a1 | 1 | 6 / 6 |
| 0.9.10.post2 | 8 (default) | 0 / 6 |

- The state itself is always correct in redis; the browser catches up only on a later delivered
  delta or the user's next click, so the loss is silent.
- Why it matters for this train: the routeless hydrate #7073 adds is exactly a backend-initiated
  delta, so in the default prod deployment the new fix is invisible to the client.
- Repro, evidence and rerun commands: `bg_rehydrate/NOTES.md` (VERIFICATION section) and
  `bg_rehydrate/verification/`.

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

## FINDING-017: `rx.plotly` still drops the `id` prop on react-plotly.js 4.1.0 (LOW, pre-existing)

- Cluster: `orch_probes` | Regression: no | Previous campaign's FINDING-020, still open.
- Repro (compile only, no server): `rx.plotly(data=go.Figure(...), id='the-plot').render()['props']`
  yields `id:"the-plot"` and no `divId`. react-plotly.js's `Plot` forwards only `divId` to the
  container div, so the id never reaches the DOM (the previous campaign confirmed that end to end).
  The 4.0.0 → 4.1.0 bump in this train does not change the mechanism.
- Evidence: `orch_probes/NOTES.md`.

## FINDING-018: one unserializable state var drops the whole hydrate delta in dev (HIGH, pre-existing)

- Cluster: `ent_aggrid` | Regression vs 0.9.10.post2: no (identical counts and messages) |
  Trigger: downstream (reflex-enterprise python-callable column defs) | Mechanism: reflex-side |
  Verifier: CONFIRMED and widened — a 40-line app with one state var holding a python-callable
  column def reproduces it with no ag_grid, no `@rx.memo`, no demo patch and none of the demo's
  routes, so it is not an artifact of the demo. The serializer raises inside the `json.dumps`
  default hook, which aborts encoding of the entire socket.io packet; and the bundled-library
  registry it validates against is only populated by a *compiling* process, so any worker started
  with `.nocompile` or `__REFLEX_SKIP_COMPILE=true` (which includes the prod backend path) sees only
  the four defaults even though the library is in the shipped bundle.
- In dev the granian worker never runs `compile_app`, so reflex-enterprise's lambda-serialization
  validation raises while the hydrate delta is being encoded. The delta is then dropped **entirely**:
  one bad var takes every other var in the state with it.
- User-visible proof from the run: click the `/formatters` row counter three times (UI shows 3),
  reload, the UI shows `0`, click once and it jumps to 4. The server had the value all along; only
  the delta was lost. Seventeen `[Reflex Backend Exception]` blocks per route sweep, each
  `ValueError: Library @radix-ui/themes is not bundled` inside
  `hydrate -> emit_delta -> _sio_dumps -> reflex_enterprise/vars.py serialize_lambda`. Loading
  `/editable` also renders a red panel quoting that internal error to the user. Prod is clean.
- Repro and evidence: `ent_aggrid/NOTES.md` ISSUE 2, `artifacts/backend_exception_hydrate_delta_a1.txt`,
  `logs/run_a1_dev.log` and `logs/run_0910_dev.log` (17 blocks each), `scripts/drive_hydrate2.py`.
- Worth a maintainer's judgment even though it is not new: the blast radius (whole delta, silent
  state revert, internal error text shown to end users) is a framework behaviour, not an enterprise one.

## FINDING-019: shipped reflex-enterprise 0.9.5 demo defects (MEDIUM, pre-existing, downstream)

- Cluster: `ent_aggrid` | Regression: no (all identical on 0.9.10.post2) | Downstream: yes — these
  belong on the reflex-enterprise tracker, not this repo's.
1. The shipped `ag_grid` demo cannot start unpatched: `formatters.py` bundles `$/utils/components`,
   so compile exits 1 with `ValueError: Library $/app_components/ag_grid/formatters is not bundled`.
   (The error is at least a clean ValueError now, where 0.9.9a1 masked it as a `VarAttributeError`.)
   Verifier correction: that path stopped being the memo library in reflex **0.9.2**, not 0.9.8 —
   0.9.2–0.9.5 used `$/utils/components/<ExportName>` and 0.9.6+ uses `$/app_components/<module>`, so
   the demo cannot start on any reflex that reflex-enterprise 0.9.5 permits (`reflex[db]>=0.9.6`).
   The verifier also found a **framework-side** half worth acting on: `compile_app()` calls
   `reset_bundled_libraries()` *after* the app module is imported (`reflex/compiler/compiler.py:1212`),
   so a user's module-scope `bundle_library()` — exactly the remedy the error message prints — is
   discarded before pages are evaluated. Present since 0.9.2; this is the previous campaign's
   FINDING-017 seen from another angle.
2. `ModelWrapper`'s datasource URL percent-encodes the `?`, so `/model`, `/model-auth` and
   `/model-ssrm` fetch `...%3FstartRow=0...` and 404 with an empty grid.
3. reflex-enterprise pins ag-grid 34.3.1 against ag-charts-enterprise 11.2.4, which AG Grid rejects,
   so integrated charts cannot be created.
4. `ag_grid.column_def()` silently drops unknown kwargs, which is why `ag_grid_finance`'s
   `checkbox_selection=True` yields no selectable rows and its chart never renders.
- Evidence: `ent_aggrid/NOTES.md` ISSUES 1, 5, 4, 7 with per-route reports under `shots/`.

## FINDING-021: one `REFLEX_USE_NPM=1` run converts a project to npm permanently (LOW, pre-existing)

- Cluster: `orch_probes` | Regression: no | Also closes the previous campaign's FINDING-018, which
  did **not** reproduce here: the npm → bun switch is clean.
- Three runs of a fresh blank app in one directory: with `REFLEX_USE_NPM=1`, npm installs everything
  under node 22 and the page is clean; the **next** run, with no env var, silently uses npm again,
  because reflex chooses the installer from the persisted lockfile; deleting
  `reflex.lock/package-lock.json` and `.web/package-lock.json` restores bun 1.4.0 and writes
  `bun.lock`. Nothing announces the sticky state, and while it lasts the project never gets the Bun
  1.4 lockfile behaviour this train ships.
- Evidence: `orch_probes/NOTES.md`, `orch_probes/logs/{npm_run,bun_after_npm,bun_after_rmlock}.trimmed.log`.

## FINDING-022: module-scope `bundle_library()` is discarded before pages are evaluated (MEDIUM, pre-existing)

- Clusters: `ent_map_dnd_flow` (pure-reflex probe), `ent_aggrid` (verifier's secondary finding), and
  the previous campaign's FINDING-017 | Regression: no (present since reflex 0.9.2)
- `compile_app()` calls `reset_bundled_libraries()` (`reflex/compiler/compiler.py:1212`) *after* the
  app module has been imported, so a `bundle_library("...")` call at module scope — the placement the
  documentation and the error message both steer users to — is wiped before any page is evaluated.
  The compile then fails with `ValueError: Library ... is not bundled. Use ... bundle_library(...)`,
  telling the user to do exactly what they did.
- Repro without reflex-enterprise: an app whose module scope calls `bundle_library("d3-format")` and
  prints the active registration context's bundled libraries at import, after `rx.App()`, and inside
  the page function; `reflex export --frontend-only --no-zip` shows the library present at import
  and gone at page evaluation. `ent_map_dnd_flow/bundlectx/`.
- Three independent observations in this campaign make this the most-corroborated framework finding.

## FINDING-023: a hook-bearing component inside `rx.foreach` compiles, then blanks the page (MEDIUM, pre-existing)

- Cluster: `ent_map_dnd_flow` | Regression: no
- Using a component that emits a React hook (here `rxe.dnd.draggable`, which emits `useDrag`) as the
  render function of `rx.foreach` compiles with no warning; the generated hook call is then hoisted
  out of the `.map()` closure while still referencing the loop variable, so the browser throws
  `ReferenceError: iid_rx_state_ is not defined at Foreach (...)` and the error boundary replaces the
  whole page. Wrapping the same body in `@rx.memo` works.
- Repro: `ent_map_dnd_flow/foreachhook/` (two routes, one broken and one memo-wrapped, plus a driver).

## FINDING-024: the error boundary logs three invalid-DOM-property errors whenever it renders (LOW, pre-existing)

- Cluster: `ent_map_dnd_flow` (also seen by `hmr_runtime`) | Regression: no
- Every time the framework's own `ErrorBoundary` fallback renders, React logs
  `Invalid DOM property 'stroke-linecap'` / `'stroke-linejoin'` / `'stroke-width'` — kebab-case
  attributes passed through `custom_attrs` at `reflex_components_core/base/error_boundary.py:85`.
  They appear *above* the real exception in the console, so the first thing a user debugging a crash
  reads is three framework warnings.

## FINDING-025: `rx.AdminDash` returns HTTP 500 on every `/admin` route (MEDIUM-HIGH, pre-existing)

- Cluster: `orch_probes` | Regression vs 0.9.10.post2: no (broken there too) | Verifier: isolated by
  the orchestrator against a plain Starlette app
- reflex 0.9.11a1 changelog: "AdminDash now works with starlette-admin 1.0 ... Both starlette-admin
  0.x and 1.x are supported." The `engine` → `session_provider` rename is handled, but the dashboard
  never serves: `/admin/`, `/admin/widget/list`, `/admin/login` and even `/admin/statics/...` all
  return 500 with `NoMatchFound: No route exists for name "admin:list"` (0.9.11a1) or
  `"admin:statics"` (0.9.10.post2).

| reflex | starlette-admin | `/admin/` |
|---|---|---|
| 0.9.11a1 | 1.0.1 / 1.0.0 / 0.17.1 | 500 |
| 0.9.10.post2 | 0.17.1 | 500 |

- Isolation: the same `Admin(engine)` + `ModelView` mounted with `mount_to()` on a plain Starlette
  1.6 app returns 200, and still 200 when that app is itself mounted at `/`. So neither starlette 1.6
  nor mount nesting explains it; the fault is in reflex's admin setup
  (`reflex/app.py:1428-1453`, mounted onto `self._api`; requests arrive via `app.py:715`).
- Repro, table and isolation script: `orch_probes/NOTES.md`, `orch_probes/adminapp/`,
  `orch_probes/admin_isolate.py`, `orch_probes/logs/admin_run_*.tail.log`.
- Maintainer decision: the AdminDash changelog entry claims a working state that no supported
  starlette-admin version delivers. Either the entry needs qualifying or `/admin` needs fixing.

## FINDING-026: custom code touching `window` breaks `reflex export` with an opaque error (LOW, pre-existing)

- Cluster: `orch_probes` | Regression vs 0.9.10.post2: no (identical failure)
- A component whose `add_custom_code()` returns `window.__x = 1;` has that statement emitted at
  module scope of the generated route, which the prerender step executes in Node. `reflex export`
  then fails with `Prerender: Request failed for /: ... Received a 500 status code from
  entry.server.tsx`, echoing an HTML error page into the build log. Nothing names the custom code,
  the component, or `window`. Guarding with `typeof window !== 'undefined'` fixes it immediately,
  which isolates the cause.
- The compiler knows which component contributed each block, so a diagnostic is cheap.
- Repro and logs: `orch_probes/NOTES.md`, `orch_probes/memoapp/`,
  `orch_probes/logs/memo_export_new.tail.log` (0.9.11a1) and `memo_export_base_window.tail.log`
  (0.9.10.post2).

## FINDING-027: reflex-otel's documented env-var setup exports nothing (MEDIUM, new feature, small fix)

- Cluster: `otel` | Regression: n/a (new package) | Changelog: reflex-otel 0.1.0a1 (#6899)
- The recipe printed verbatim in reflex-otel's README and in `docs/api-reference/observability.md`
  installs `opentelemetry-exporter-otlp-proto-http` and then sets `OTEL_TRACES_EXPORTER=otlp`. With
  opentelemetry-sdk 1.44.0 that name resolves to **otlp_proto_grpc**, which the documented pip line
  does not install. `_configure_sdk_from_environment()` logs the whole traceback (twice) and
  `_instrument()` continues, so the app reports otel enabled while sitting on a `ProxyTracerProvider`
  and the collector is never contacted.
- Fix is small: document `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` (or install the grpc exporter, or
  default the protocol when only the http exporter is present), and treat the configuration failure as
  fatal rather than continuing with tracing "enabled".
- Evidence: `otel/evidence/run9-readme-env-traceback.txt`, `run9-receiver-access-EMPTY.log`.
- Everything else in the recipe space works: programmatic providers and
  `opentelemetry-instrument reflex run` both export correctly, as does the browser plugin.

## FINDING-028: the initial `reflex.compile` span tree is never exported in dev (LOW, new feature)

- Cluster: `otel` | Regression: n/a | Changelog: reflex-base 0.9.11a1 (#6900), README "one
  `reflex.compile` span per app compile ... with the stages as child spans"
- Under dev `reflex run` the initial compile happens in a `ProcessPoolExecutor` worker that exits via
  `os._exit`, so neither `atexit` nor provider shutdown runs: with OTLP the tree never arrives, and
  with a fast batch processor only two stage children escape, pointing at a parent span id that was
  never exported. Prod, `reflex export` and hot reload all export the full tree.
- Evidence: `otel/evidence/compile-span-loss.txt`, `run1-spantree.txt`.

## FINDING-029: reflex-otel upgrades reflex-base out from under reflex (LOW, new package metadata)

- Cluster: `otel` | Regression: n/a
- `reflex-otel` depends on `reflex-base>=0.9.11a1` but not on `reflex`, so installing it into a
  reflex 0.9.10.post2 environment silently upgrades reflex-base to 0.9.11a1 and breaks reflex's
  exact pin. No error, no warning; `uv pip check` afterwards reports the incompatibility. The mixed
  environment imports fine and produces partial telemetry, because reflex 0.9.10.post2 has no otel
  call sites — the confusing outcome of "it installed, so it should work".
- Evidence: `otel/evidence/mixed-env-0910-plus-otel.txt`.

## Cluster summaries

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

### `ent_aggrid` (pass 28, fail 8, anomaly 4, skipped 1) — NO REGRESSION; the 0.9.9a1 enterprise breakage is fixed
The 17-route ag_grid demo and the `ag_grid_finance` example behave identically on 0.9.11a1 and
0.9.10.post2, dev and prod (per-route action lists diff to zero). Last campaign's FINDING-001/021/022/023
are fixed twice over: reflex restored `dynamic.bundled_libraries` and `page.DECORATED_PAGES` as
deprecation shims, and reflex-enterprise 0.9.5 reads bundled libraries from the RegistrationContext.
Python-callable renderers and formatters, `@rx.memo` row counters, `@rxe.static` dialogs, cell editing,
master-detail, tree data, pivot, selection, fill handle, grid-state round-trip and the finance app's
fetch/pagination/filter/sort all work. Every failure is pre-existing (FINDING-018, FINDING-019).

### `otel` (pass 31, anomaly 9, fail 3) — the new package works; three defects, one small and worth fixing now
The whole OpenTelemetry surface was exercised end to end with a hand-written OTLP receiver: one span
per handler run named after the event, CONSUMER for websocket events with INTERNAL chained children
three levels deep, recorded exceptions, `session.id` as a truncated hash with the raw token absent
from the export, `/ping` excluded, the websocket token query parameter redacted, all four `reflex.*`
metrics plus the ASGI middleware's, browser PRODUCER spans joining the backend trace over both the
websocket and uploads, web vitals and React render timing, prod mode, hot reload, nine granian
workers, a second `instrument()` as a no-op, and hostile client trace context handled safely.
Inertness holds: `import reflex` pulls in no opentelemetry modules even with reflex-otel installed.
The three FAILs are FINDING-027, FINDING-028 and FINDING-029. Also worth a maintainer's eye: the
PR descriptions for #6899 and #6901 describe behaviour the shipped code does not have (SERVER vs
CONSUMER span kind, and an endpoint fallback that was deliberately dropped), while README and docs
are correct — release notes assembled from PR text would inherit the errors.

### `ent_map_dnd_flow` (pass 11, anomaly 8, skipped 5, fail 2) — NO REGRESSION; four 0.9.9a1 breakages fixed
map, dnd and flow run unmodified on 0.9.11a1 with reflex-enterprise 0.9.5: map 13/13 plus 7 new checks,
dnd 18/18 (identical on a real 0.9.10.post2 baseline), flow 11/11 plus 9 new deletion/persistence
checks, and a purpose-built map+dnd+flow app at 20/20, with zero page errors, console errors, 4xx/5xx
or server tracebacks. Last campaign's FINDING-001/021/022/023 are all fixed, including a `can_drop`
lambda pulling `format` from a bundled `d3-format` driving real drops in the browser. The two FAILs
are FINDING-022 and FINDING-023. **Coverage gap, recorded honestly**: prod mode could not be tested
on either version, because reflex-enterprise gates `reflex run --env prod` and `reflex export` behind
a paid subscription that `CI=1` does not bypass, and the agent declined to set the app-harness flag
purely to get around a licence check.

### `orch_probes` (orchestrator) — 2 fixed items confirmed, 4 pre-existing gaps
AppHarness now names `reflex[testing]` in its error (previous FINDING-016 fixed); `reflex_base.otel`
is genuinely inert without reflex-otel; all 34 `reflex cloud` leaf commands return off a TTY with
clean single-document JSON on stdout. Gaps: FINDING-012 to FINDING-015.

### `up_counter_todo_clock` (pass 18, anomaly 8, skipped 1) — no regression except FINDING-002
counter, todo, clock, linkinbio: baseline → in-place → cold identical (md5-identical screenshots),
Bun 1.3.11→1.4.0 migration clean, lockfile stays v1, `context.js` removed, package.json diff is
exactly the announced pins.

### `ent_mcp_oidc` (solo) — NO REGRESSION on the two surfaces the user named
The enterprise MCP plugin and the whole OIDC flow, driven against a purpose-built local OIDC
provider (discovery, JWKS, PKCE S256, refresh, userinfo, RP-initiated logout). 22 recorded browser
steps **byte-identical** across reflex 0.9.11a1 and 0.9.10.post2; the MCP protocol runs differ only
in delta key ordering (FINDING-030). Protected-value withholding, page and handler guards
(foreground and background), reload and second-tab persistence, and an anonymous MCP session
correctly scoped to `auth=False` handlers all hold. Two pre-existing MCP-resource quirks:
FINDING-031, FINDING-032.

### `components_bumps` — ONE REGRESSION (FINDING-033), everything else clean
All six bumped component libraries in dev and prod against the previous stable. The moment bump
leaks a literal `locale=` to every other `rx.moment` on the page; code/plotly/radix/recharts/sonner
behave the same as or better than 0.9.10.post2. Seven pre-existing rough edges: FINDING-034.

### `up_dataviz_local_lorem` (solo) — no regression on in-place upgrade
`local-component`, `lorem-stream` and `data_visualisation` upgraded in place — same venv, same app
directory, same `.web/`, same sqlite database. Two of the three are step-for-step identical; the
third differs only in random lorem word counts. Also verified `reflex-release` 0.1.1a1 against a
real worktree of the release branch.

### `ent_mantine_highcharts_tickets` (solo) — no regression; enterprise sweep complete
`mantine`, `highcharts` and `tickets` identical across versions on every structural count and
route. The tickets demo's `EventHandlerAPIPlugin` works over REST (bearer, delta, persisted row)
but 500s on its own OpenAPI document (FINDING-035), and every page logs a delta addressed to
substates it has no dispatcher for (FINDING-036).

### `config_assets_cli` (solo) — both claims hold, no findings
#7039's stale-link half is a clean pass/fail and 0.9.11a1 fixes it (0.9.10.post2 keeps serving the
wrong file); its concurrent-first-create half could not be provoked on this filesystem on either
version. #7050 CLI startup is ~2.3× faster on every subcommand.

### `frontend_path_ssr` (solo) — #7044 verified, one pre-existing find
`reflex export` and `reflex run --env prod` with `frontend_path` + `REFLEX_SSR=false` fail on
0.9.10.post2 with exactly the documented `FileNotFoundError` and succeed on 0.9.11a1; the prod
deployment then works end to end in a browser under the sub-path. Every route but `/` is answered
with HTTP 404 under `REFLEX_SSR=false` on both versions: FINDING-037.

### `telemetry_ctx` (solo) — #6960 verified, no findings
An `rxconfig.py` that logs its importing thread shows the re-import on `reflex-telemetry_0` under
0.9.10.post2 and its absence under 0.9.11a1.

### `memo_hash` (solo) — #6947 verified, no findings
Two `AppHarness` apps compiled in one pytest process, each with a same-named `rx.memo` used under
`rx.foreach`, emit distinct memoized names while still sharing the names of genuinely identical
framework components; neither app's output is disturbed by the other's compile. 5/5 checks pass.


## FINDING-030: state-delta key ordering changed between 0.9.10.post2 and 0.9.11a1 (LOW, new)

Within a single state's delta object, 0.9.11a1 emits computed vars before base vars where
0.9.10.post2 emitted them after, and the order of the per-state entries in a multi-state delta
differs too. Same keys, same values — JSON object order is not semantic — but any downstream
golden-file or snapshot test that compares a serialised delta as text will break on upgrade.

Repro (`ent_mcp_oidc/`, both venvs, no browser needed):

```
cd apps/mcpapp && reflex run --backend-only --backend-port 9801     # 0.9.11a1
python scripts/mcp_drive.py 9801 | diff - <(...same on 0.9.10.post2...)
```

Evidence `ent_mcp_oidc/logs/a1_drive2.log` vs `logs/0910_drive.log`, `add(5)` delta:

```
0.9.10.post2: {"count": 6, "uncached_marker": "c=6", "doubled": 12, "history": [1, 6]}
0.9.11a1:     {"doubled": 12, "uncached_marker": "c=6", "history": [1, 6], "count": 6}
```

and for a two-state delta the `profile_state` entry moved ahead of the `counter_state` entry.
The 41 diff lines between the two runs are *entirely* this reordering; `mcp_probe2.py` output is
byte-identical. Not a regression in behaviour — filed so the release notes can mention it if any
downstream project snapshots deltas.

## FINDING-031: `reflex://state/events/<unknown state>` returns an empty list instead of an error (LOW, pre-existing, reflex-enterprise)

The two `reflex://state/...` resource families disagree about unknown state names, and neither
accepts the state name that `search_events` hands the caller.

* `reflex://state/vars/<unknown>` → a helpful `Unknown state '...'. Use a fully-qualified state
  name from reflex://state (the root is reflex___state____state).`
* `reflex://state/events/<unknown>` → `{"state": "totally___bogus___state", "events": []}` — a
  plausible-looking answer that an agent will read as "this state has no handlers".

The trap is that `search_events` and `reflex://event` report `"state":
"mcpapp___mcpapp____counter_state"`, but the resources require the root-prefixed
`reflex___state____state.mcpapp___mcpapp____counter_state`. Copying the field straight out of the
tool result therefore yields an error from one resource and a silent empty list from the other.

Repro: `ent_mcp_oidc/scripts/mcp_drive.py` (steps `read reflex://state/events/...` and `read
events of BOGUS state`), evidence in `logs/a1_drive2.log`; identical on 0.9.10.post2
(`logs/0910_drive.log`), so pre-existing in reflex-enterprise 0.9.5, not a 0.9.11a1 regression.

## FINDING-032: a withheld protected field is served to MCP as its default, with no signal (LOW, pre-existing, reflex-enterprise)

With `AuthPlugin` active and an anonymous MCP session, the two kinds of protected member behave
differently on read:

* protected **computed var** → `'secret_label' on '...' is not accessible for the current session
  (it is protected and the session is not authorized for it)` — explicit.
* protected **field** → `{"var": "secret_note", "computed": false, "value": "top-secret"}` — the
  default value, indistinguishable from the real one.

In the repro the server-side value at that moment is `FIELD-SECRET` (a public handler wrote it),
so withholding is working; the problem is only that the caller is told nothing. An agent reading
`secret_note` will act on `top-secret` believing it is live state.

Repro: `ent_mcp_oidc/scripts/mcp_auth_probe.py <backend_port>` against `apps/authapp`; evidence
`logs/a1_mcp_auth.log` (`queue authapp___authapp____public_state.poison_field` shows the delta
carrying the filtered `"secret_note": "top-secret"`, then `read secret_note` returns the same).
Identical on 0.9.10.post2 (`logs/0910_mcp_auth.log`) — pre-existing, enterprise-side.

## FINDING-033: one `rx.moment(locale=...)` changes the language of every other `rx.moment` on the page (MEDIUM, **regression**, reflex-components-moment 0.9.4a1)

`reflex-components-moment` 0.9.4a1 bumps `react-moment` 1.2.2 → 2.0.2, and with it a literal
`locale=` on one component now sets the language for every moment on the page that does not name
its own locale.

```python
rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", id="plain")    # no locale prop
rx.moment("2020-01-01T00:00:00", from_now=True, id="fromnow")              # no locale prop
rx.moment("2024-03-14T15:09:26", format="dddd D MMMM YYYY", locale="fr", id="french")
```

| stack | `plain` | `fromnow` |
| --- | --- | --- |
| 0.9.11a1 + components-moment **0.9.4a1** | `jeudi 14 mars 2024` | `il y a 7 ans` |
| 0.9.10.post2 + components-moment 0.9.3 | `Thursday 14 March 2024` | `7 years ago` |

Bisected to the component bump alone: reflex **0.9.11a1 core with components-moment 0.9.3** does
not leak (`components_bumps/results/out_mixed/moment.json`). Reproduced in dev *and* prod, and it
survives a reload.

Mechanism: for a literal `locale=` the wrapper emits a side-effect `import "moment/locale/fr"`,
and moment's `defineLocale` makes that locale the process-wide default. Both react-moment versions
fall back to `moment.locale()` for a component with no `locale` prop, but under 1.2.2 the app-wide
default was still `en` at render time and under 2.0.2 it is `fr`.

It depends on import order, which is why it looks random: with a **Var** locale the wrapper pulls
in `moment/min/locales`, whose bundle ends by restoring `en`, and the same page does not leak — so
an app can start leaking by adding or removing an unrelated moment component.

Repro: `components_bumps/leakapp2/` plus `components_bumps/scripts/drive_leak.py`; evidence
`components_bumps/results/out_dev/moment.json` vs `results/out_base/moment.json`, screenshots
`components_bumps/shots/`. Suggested direction: stop relying on the global — pass an explicit
locale per component (or react-moment 2.x's `<MomentProvider locale=...>`), or restore the previous
default after importing a locale file.

## FINDING-034: seven pre-existing component-library rough edges surfaced by the bump sweep (LOW, all pre-existing)

Found while exercising the six bumped component libraries; every one reproduces identically on
0.9.10.post2, so none is a regression. Full detail and repros in `components_bumps/NOTES.md`
(ISSUE-2 … ISSUE-10).

* `rx.form.message(force_match=...)` without `match` is always visible and logs a React DOM error
  (upstream radix).
* Three emotion `":first-child" ... server-side rendering` console errors on the radix page in dev.
* Moment locale imports log a `defineLocale` deprecation warning in the browser *and* the server log.
* Unsupported `rx.moment` props are silently turned into CSS (by design, but silent).
* plotly `layout={"title": "..."}` as a plain string renders no title (upstream plotly.js 3.x).
* recharts axes have no `tick_formatter`; the unsupported prop is swallowed as a style.
* Adding `rx.toast.provider` to a page renders every toast twice; `ToastAction` is not importable
  from `rx`; `on_submit` form data includes every child `id=` as a null key.

## FINDING-035: the enterprise event-handler API serves a 500 for its own OpenAPI document (LOW, pre-existing, reflex-enterprise)

`rxe.EventHandlerAPIPlugin` publishes an OpenAPI spec at `/_reflex/events/openapi.yaml` and
advertises it from `/.well-known/api-catalog`. The catalog works; the document it points at
returns `500 Internal Server Error` on a clean install:

```
File ".../reflex_enterprise/plugins/event_handler_api.py", line 1686, in openapi_response
  schema = schemas.get_schema(routes=routes)
  ...
  assert yaml is not None, "`pyyaml` must be installed to use parse_docstring."
AssertionError: `pyyaml` must be installed to use parse_docstring.
```

starlette's `SchemaGenerator` needs PyYAML, and nothing in the dependency chain pulls it in —
`pyyaml` is absent from every venv built for this campaign (`reflex`, `reflex[db]`,
`reflex-enterprise`, `reflex-enterprise[mcp]`); starlette declares it only under its `full` extra.

Repro: run `reflex-enterprise/demos/tickets` (`ent_mantine_highcharts_tickets/runpair.sh tickets
ent 5452 9852 a1 / /ticket`), then
`curl -L http://localhost:9852/_reflex/events/openapi.yaml` → 500 on **both** reflex 0.9.11a1 and
0.9.10.post2, so pre-existing, not a regression.

Confirmed fix: `uv pip install pyyaml` into the same venv and the endpoint returns a 27 KB
document (`ent_mantine_highcharts_tickets/out/tickets_openapi_with_pyyaml.yaml`). Declaring
`pyyaml` (or `starlette[full]`) alongside the plugin is all it needs. The REST event API itself is
unaffected — `POST /_reflex/event/<state>/<handler>` with an app-issued bearer returns 200, the
delta, and a persisted row.

## FINDING-036: a delta is sent for substates the page has no dispatcher for (LOW, pre-existing)

Every page of the enterprise `tickets` demo logs, twice, on both reflex versions:

```
Cannot process state update: no dispatch function for substate(s)
"reflex___state____state.reflex_enterprise___auth___oidc___state____generic_oidc_auth_state",
"reflex___state____state.reflex_enterprise___auth___oidc___state____is_iframed_state". Try ...
```

The app configures no auth plugin; importing `reflex_enterprise` is enough to define those states,
and the backend then includes them in the delta while the compiled page carries no dispatcher for
them. Nothing visibly breaks, but every user of an enterprise app sees two console errors on every
page load, and a real delta addressed to a missing substate would be swallowed the same way.

Repro and evidence: `ent_mantine_highcharts_tickets/out/tickets_a1.json` and
`out/tickets_base_base.json`, `console_errors` in each. Identical on 0.9.10.post2 — pre-existing.

## FINDING-037: with `REFLEX_SSR=false`, every prod route but `/` is served as HTTP 404 (LOW, pre-existing)

Route prerendering off (`REFLEX_SSR=false`, or `reflex export --no-ssr`) leaves the prod server with
a single prerendered document, and it answers every other path with **404 plus the SPA HTML**. The
browser is fine — the client router reads the URL and renders the right page — but the status line
says the page does not exist, and a real route is indistinguishable from a typo'd one.

Measured on the reflex prod server, four configurations
(`frontend_path_ssr/logs/route_status_matrix.txt`, reproduce with
`frontend_path_ssr/probe_routes.sh <port> <prefix>`):

| config | `/` | `/about` (a real page) | `/nosuchroute` |
| --- | --- | --- | --- |
| `frontend_path=/myapp`, `REFLEX_SSR=false`, 0.9.11a1 | 200 | **404** | 404 |
| `frontend_path=/myapp`, SSR on, 0.9.11a1 | 200 | 307 → 200 | 404 |
| no `frontend_path`, `REFLEX_SSR=false`, 0.9.11a1 | 200 | **404** | 404 |
| no `frontend_path`, `REFLEX_SSR=false`, 0.9.10.post2 | 200 | **404** | 404 |

`frontend_path` is not the trigger and this is not a regression — the previous stable does the same.
It matters because `REFLEX_SSR=false` is exactly the configuration #7044 makes usable with
`frontend_path` in this release, so more people are about to run it: crawlers will drop the routes,
uptime checks and CDNs will treat live pages as errors, and `curl` gives no way to tell a real route
from a dead one. Serving the fallback document with 200 for a known route (and keeping 404 for
genuinely unknown paths) would fix it.


## FINDING-038: MCP `search_events` advertises a `rest_path` that 404s without `EventHandlerAPIPlugin` (LOW, pre-existing, reflex-enterprise)

Every `search_events` result carries `"rest_path": "/_reflex/event/<state>/<handler>"`, built
unconditionally by `reflex_enterprise/plugins/event_handler_api.py:507 describe_event_handler`,
which the MCP plugin reuses. With `rxe.MCPPlugin()` alone — the configuration the MCP docs show —
that route is not mounted, so an agent that follows the advertised path gets a bare `404 Not Found`
with nothing saying the REST surface is disabled.

Repro: `ent_mcp_oidc/apps/authapp` plus `ent_mcp_oidc/scripts/mcp_extra_probe.py <backend_port>`;
evidence `ent_mcp_oidc/logs/mcp_extra_a1.json` (`rest_event_path` → 404 with and without a valid
bearer) and `logs/mcp_extra_0910.json`, identical on reflex 0.9.10.post2 — a property of the
reflex-enterprise 0.9.5 wheel, not a regression. Omitting `rest_path` (or marking it unavailable)
when the REST plugin is not mounted would fix it.

## FINDING-039: logout from an iframed app never reaches the IdP's `end_session_endpoint` (LOW-MEDIUM, pre-existing, reflex-enterprise)

In the popup (iframed) logout flow the provider session is never ended, so single sign-out does not
happen: the local session is cleared and the popup closes, but the IdP is never told, and clicking
login again silently re-authenticates from the surviving IdP session.

Mechanism (`reflex_enterprise/auth/oidc/state.py`, `redirect_to_logout`): when `_use_popup_flow()`
is true the opener yields `redirect_to_logout_popup` and then **immediately** awaits
`self._reset_session()`. The popup's `/popup-logout` page runs `set_from_popup(True)` +
`redirect_to_logout` on load, by which time the shared cookies are gone, so `has_any_token` is
false and it takes the "Re-entry after provider logout completed; just close" branch — `CLOSE_POPUP`,
no IdP round trip. The server log shows `Processing logout flow (from_popup=False)` followed by
`(from_popup=True)`.

Repro: run the shipped `reflex-enterprise/demos/oidc` against `ent_mcp_oidc/idp/fake_idp2.py`, then
`ent_mcp_oidc/scripts/drive_popup_logout.py <frontend_port>`; the IdP's `/_log` shows the
`GET /authorize` of the login but **no `GET /logout`**, while the non-iframed logout in
`scripts/drive_oidc_demo.py` does produce `GET /logout` with `id_token_hint` and
`post_logout_redirect_uri`. Reproduced identically on reflex 0.9.10.post2 — pre-existing.
