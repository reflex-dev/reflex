# ent_aggrid — reflex-enterprise 0.9.4 ag_grid demo vs reflex 0.9.9a1

Agent cluster: `ent_aggrid`. Tested 2026-08-28.
Packages (all from PyPI): `reflex-enterprise==0.9.4` against `reflex==0.9.9a1`
(reflex-base 0.9.9a1) and baseline `reflex==0.9.8` (reflex-base 0.9.8).
Demo source: `/home/user/reflex-enterprise/demos/ag_grid` (read-only reference; copied here).

## Layout of this artifact dir

- `demo_a1/` — demo copy run against reflex 0.9.9a1 (contains the two demo patches
  described below plus the "formatters page disabled" patch in `ag_grid/ag_grid.py`)
- `demo_098/` — demo copy run against reflex 0.9.8 (same two demo patches, formatters ENABLED)
- `minimal/` — minimal repro app (one `rxe.ag_grid`; `REPRO_LAMBDA=1` adds one
  lambda `cell_renderer` column that reproduces the 0.9.9a1 compile crash)
- `drive_aggrid.py` / `drive_minimal.py` — Playwright drivers
- `probe_pages.py` / `probe_coldefs.py` — offline per-page / per-column-def crash probes
- `logs/` — full server logs for every run
- `artifacts/` — extracted tracebacks, package.json snapshots + diff
- `shots_098/`, `shots_a1/`, `shots_minimal/` — screenshots + `report.json`
  (per-route actions, console errors/warnings, failed network requests)

## Setup / rerun instructions

```bash
cd demo_a1   # or demo_098
uv venv venv --python 3.11
uv pip install --python venv/bin/python --prerelease=allow \
    'reflex==0.9.9a1' 'reflex-enterprise==0.9.4' -r requirements.txt   # 0.9.8 for baseline
# DB init (alembic.ini was pointed at sqlite:///reflex.db; placeholder URL upstream):
./venv/bin/alembic upgrade head
# rxe demands login; CI=1 bypasses AppEnterprise._check_login()'s exit():
CI=1 REFLEX_TELEMETRY_ENABLED=false ./venv/bin/reflex run --loglevel debug \
    --frontend-port 3300 --backend-port 8300   # 3301/8301 used for 0.9.8
# drive (Playwright, chromium at /opt/pw-browsers/chromium):
NO_PROXY=localhost,127.0.0.1 python drive_aggrid.py http://localhost:3300 shots_out
```

Minimal repro (no DB needed):

```bash
cd minimal
CI=1 REPRO_LAMBDA=1 REFLEX_TELEMETRY_ENABLED=false <venv>/bin/reflex run \
    --loglevel debug --frontend-port 3302 --backend-port 8302
# on 0.9.9a1: exits during "Compiling" with
#   reflex_base.utils.exceptions.VarAttributeError: Attribute _cached_get_all_var_data not found.
# on 0.9.8: runs; lambda column renders (shots_minimal/min_lambda_098.png)
# without REPRO_LAMBDA: runs fine on BOTH versions (plain grid, sort works).
```

Offline probes (no server, seconds instead of minutes):

```bash
cd demo_a1 && CI=1 PYTHONPATH=$PWD ./venv/bin/python ../probe_pages.py    # which page crashes
cd demo_a1 && CI=1 PYTHONPATH=$PWD ./venv/bin/python ../probe_coldefs.py  # which column def crashes
```

## FINDINGS

### 1. REGRESSION (HIGH): lambda/python-function grid props crash app compile on 0.9.9a1 — FINDING-001 end-to-end confirmation

- Root cause is exactly FINDING-001: `reflex_enterprise/vars.py:143`
  (`bundled_libraries = set(dynamic.bundled_libraries)` inside
  `LiteralLambdaVar._validate_and_extend_return_expr`) reads
  `reflex.components.dynamic.bundled_libraries`, removed by reflex-base 0.9.9a1 (#6382).
- BUT the user never sees that AttributeError. The read happens inside the computation of
  `CachedVarOperation._cached_get_all_var_data` (a custom `cached_property`); the
  AttributeError escaping a descriptor `__get__` makes Python fall back to
  `Var.__getattr__`, which raises
  `reflex_base.utils.exceptions.VarAttributeError: Attribute _cached_get_all_var_data not found.`
  with NO chained cause. The real error is completely masked (see finding 2).
  Full tracebacks: `artifacts/traceback_demo_a1_masked_varattributeerror.txt` (demo),
  `artifacts/traceback_minimal_a1.txt` (minimal app).
- Trigger granularity, established with `probe_coldefs.py`: a column def whose
  `cell_renderer`/`value_formatter` is a python callable AND whose compiled return
  expression carries imports:
  - `cell_renderer=lambda params: rx.text(...)` — CRASH (component import)
  - `cell_renderer=lambda params: row_counter(...)` (`@rx.memo`) — CRASH
  - `value_formatter=flag_formatter` (uses `Var.create({...}).get(...)` whose JS
    helper needs an import) — CRASH
  - `value_formatter=lambda params: round(params.value.to(float), 4)` — OK (no imports)
  - `value_formatter=currency_formatter` (string ops only) — OK
  - plain-string / FunctionStringVar formatters and getters — OK
- Only 1 of 17 demo pages (`/formatters`) contains crashing constructs, but ONE bad page
  aborts the WHOLE app compile, so the demo as a whole is dead on 0.9.9a1.
- A/B proof with byte-identical app code (after the demo fixes of finding 3):
  0.9.8 compiles and all 17 routes work end-to-end in Chromium; 0.9.9a1 exits at
  "Compile pages" with the masked VarAttributeError.
- With the formatters page disabled (`demo_a1/ag_grid/ag_grid.py`), the OTHER 16 routes
  work on 0.9.9a1 exactly like on 0.9.8 (same row counts, sorting, cell editing incl.
  on_cell_value_changed toast, master-detail expand, tree expand, selection checkboxes,
  state-driven column/data loading, grid-state serialization, pivot, integrated charts;
  compare `shots_a1/report.json` vs `shots_098/report.json`).
- A trivial `rxe.App` + `rxe.ag_grid` with no python-callable props works fine on
  0.9.9a1 end-to-end (`shots_minimal/min_plain_a1.png`), so the breakage is confined to
  the LambdaVar path — but that path is core to ag-grid's formatter/renderer story
  (and is also used by map/dnd per FINDING-001).

### 2. ANOMALY (MEDIUM, reflex-base, not new in 0.9.9a1): CachedVarOperation masks AttributeError raised inside cached computations

- Any `AttributeError` raised while computing `_cached_get_all_var_data` /
  `_cached_var_name` (custom `cached_property` in `reflex_base/vars/base.py`) is
  swallowed by the descriptor protocol and re-surfaced as
  `VarAttributeError: Attribute _cached_get_all_var_data not found.` with no `__cause__`.
  Diagnosing finding 1 required patching `cached_property.__get__` to see the real error.
- Suggested direction (not applied): catch `AttributeError` inside
  `cached_property.__get__` (or the cached function wrapper) and re-raise as
  `RuntimeError`/chained error so real failures aren't converted into bogus
  attribute-lookup misses.

### 3. DEMO BUGS (independent of 0.9.9a1 — demo is broken on reflex 0.9.8 too, as shipped)

The shipped demo crashes at compile on PLAIN reflex 0.9.8 + rxe 0.9.4:
`ValueError: Library $/app_components/ag_grid/formatters is not bundled.`
(traceback: `artifacts/traceback_demo_098_shipped_bundle_path.txt`). Two distinct causes:

- a. `formatters.py` line 16 bundles `"$/utils/components"`, but since reflex 0.9.8
  `@rx.memo` components are emitted under `$/app_components/<module path>`, so the
  memo renderer's real library is never bundled -> the compile ValueError above.
  Worse, keeping the stale path bundled injects `import '$/utils/components'` into
  `.web/app/root.jsx`, which vite cannot resolve -> HTTP 500 on EVERY route
  (observed in the intermediate run where both paths were bundled at import time).
- b. Fix applied in both copies (`ag_grid/formatters.py`): `_bundle_renderer_libraries()`
  bundles `$/app_components/ag_grid/formatters` (stale path dropped), called BOTH at
  import time and from `formatter_page()`. The page-eval call is belt-and-suspenders:
  `compile_app()` (reflex/compiler/compiler.py:1202 on 0.9.8) calls
  `reset_bundled_libraries()` after the app module import and before compiling pages,
  wiping import-time `bundle_library` calls from the live list (verified: the entry is
  gone from `dynamic.bundled_libraries` after reset). In practice serializer/var caching
  can let an import-time-validated lambda pass anyway (offline probe
  "VALIDATION PASSED" after a manual reset), so the exact failure boundary is fuzzy —
  but rxe's own error-message advice (import-time `bundle_library`) is unreliable on
  reflex >= 0.9.8.
- c. Related runtime anomaly on 0.9.8: with the compile fixed, the backend worker logs
  `[Reflex Backend Exception] ... ValueError: Library @radix-ui/themes is not bundled`
  whenever it serializes `FormatterState.cols_defs` (state var holding lambdas) during
  event processing — the worker process never runs `compile_app`, so the radix plugin's
  `bundle_library("@radix-ui/themes")` never executed there
  (`artifacts/backend_exception_098_state_lambda_serialization.txt`). The
  formatters page still renders (Inline tab), but the "State" tab's column defs never
  reach the client. Same class of bundled-libraries state-desync, worth an rxe issue.

### 4. BASELINE BUG (both versions, "broken anyway"): ModelWrapper data endpoint 404 — `?` percent-encoded

- `/model`, `/model-auth`, `/model-ssrm` grids never load rows on 0.9.8 NOR 0.9.9a1:
  every datasource fetch goes to
  `http://localhost:<backend>/abstract-wrapper-data%3FstartRow=0&endRow=50&...` (note `%3F`)
  and gets HTTP 404. Root cause in `reflex_enterprise/utils.py:get_backend_url`: it
  assigns `path + "?query"` to `URL.pathname`; per the URL spec the `pathname` setter
  percent-encodes `?`, so the query string becomes part of the path and Starlette's
  `/abstract-wrapper-data` route never matches.
- Identical failure signature on both reflex versions (see `failed` arrays for those
  routes in `shots_098/report.json` and `shots_a1/report.json`) => NOT a 0.9.9a1
  regression; rxe 0.9.4's infinite-row ModelWrapper appears broken with any
  current reflex. (DB was initialized and reachable; the request never reaches the route.)

### 5. Environment quirks (context, not bugs)

- rxe requires login: `AppEnterprise._check_login()` calls `exit()` when tier is
  anonymous. `CI=1` (or backend-only) bypasses. All runs here used `CI=1`.
- `alembic.ini` ships with placeholder `sqlalchemy.url`; pointed at `sqlite:///reflex.db`
  and ran `alembic upgrade head` (creates `friend` table). The DB starts empty; model
  pages would show 0 rows even without finding 4.
- AG Grid Enterprise trial banner ("License Key Not Found") is printed as console
  ERRORS on every enterprise-feature page (14-42 per page) — benign/expected without
  a license key, on both versions.
- Deprecation warnings on both versions: `@rx.memo` without annotations
  (formatters.py row_counter), `rx.Model` (used by model wrapper demos),
  strings in `disable_plugins`, implicit Radix themes; on 0.9.9a1 additionally
  rxe's use of `console.error`/`console.info` is flagged deprecated.
- `/editable` toast count differed (baseline 2 vs a1 1) — sonner renders a
  stacked duplicate intermittently; cell edit + state update itself identical.

## package.json (frontend deps) 0.9.8 vs 0.9.9a1

`artifacts/package_098.json` vs `artifacts/package_a1.json`, diff in
`artifacts/package_json.diff`. Framework-level changes: react-router 7.18.2 -> 8.3.0
(react-router-dom dropped), vite 8.0.16 -> 8.2.0, postcss override removed.
(moment/react-moment absent from the a1 build only because the formatters page — the
sole rx.moment user — was disabled there.)

## Test matrix summary

| Check | 0.9.8 | 0.9.9a1 |
|---|---|---|
| shipped demo compile | FAIL (ValueError: $/app_components/ag_grid/formatters not bundled) | FAIL (masked VarAttributeError) |
| demo + bundling fixes compile | PASS | FAIL (masked VarAttributeError) — REGRESSION |
| 16 non-formatter routes E2E | PASS (all interactions) | PASS (formatters disabled; identical behavior) |
| /formatters E2E (fixed demo) | PASS (all 3 def styles, memo renderer clickable) | impossible (compile fails) |
| /model, /model-auth, /model-ssrm data load | FAIL (404 %3F) | FAIL (404 %3F) — broken anyway |
| minimal plain rxe.ag_grid | PASS | PASS |
| minimal + lambda cell_renderer | PASS | FAIL at compile — REGRESSION (minimal trigger) |

## VERIFICATION (independent, 2026-08-28, verifier agent)

Verdict: **CONFIRMED** — genuine regression, reproduced from scratch with fresh PyPI
installs (`uv venv --python 3.11`; `reflex==0.9.9a1` + `reflex-enterprise==0.9.4` vs
`reflex==0.9.8` + `reflex-enterprise==0.9.4`), using a copy of `minimal/` in an
independent working dir with different ports (3800/8800 a1, 3801/8801 baseline).
Scripts/logs/screenshots: `verification/`.

What was reproduced (all match the claim):

1. **Direct proof, no server needed** (`verification/probe_direct.py`, a1 venv):
   `LiteralLambdaVar.create(lambda params: rx.text(params.value, color="tomato"))`
   raises at `reflex_enterprise/vars.py:143`:
   `AttributeError: module 'reflex.components.dynamic' has no attribute
   'bundled_libraries'. Did you mean: 'bundle_library'?`
   Also confirmed `hasattr(reflex.components.dynamic, "bundled_libraries")` is
   False on 0.9.9a1 and True on 0.9.8.
2. **End-to-end compile crash on 0.9.9a1**: `REPRO_LAMBDA=1 CI=1 reflex run` exits 1
   during "Compile pages" with
   `VarAttributeError: Attribute _cached_get_all_var_data not found.` and the real
   `bundled_libraries` AttributeError appears NOWHERE in the debug log
   (`grep -c bundled_libraries run_a1_lambda.log` == 0) — masking confirmed
   (`verification/run_a1_lambda.log`).
3. **Masking mechanism confirmed in installed source**: `_cached_get_all_var_data` is
   reflex_base's custom `cached_property` (`reflex_base/vars/base.py:1999`); an
   AttributeError escaping its `__get__` computation triggers Python's `__getattr__`
   fallback -> `CachedVarOperation.__getattr__` -> `Var.__getattr__` ->
   `VarAttributeError` with the original exception swallowed (no `__cause__`).
   Agreed this masking pattern itself is pre-existing (same code shape on 0.9.8).
4. **Root cause proof** (`verification/probe_shim.py`): assigning
   `dynamic.bundled_libraries = RegistrationContext.ensure_context().bundled_libraries`
   before `LiteralLambdaVar.create` removes the AttributeError and restores rxe's
   intended validation (its designed "Library @radix-ui/themes is not bundled ...
   bundle_library(...)" ValueError outside app-compile context).
5. **Baseline A/B**: identical app on 0.9.8 + rxe 0.9.4 compiles ("Compiling: 100%
   14/13"), serves, and the lambda `cell_renderer` renders in Chromium: 3 styled
   nodes in the "fancy" column with computed color rgb(255, 99, 71) (tomato), zero
   console errors (`verification/verify_098_lambda.png`). NOT pre-existing.
6. **Scope check**: same app without `REPRO_LAMBDA` on 0.9.9a1 runs and renders the
   plain grid end-to-end, zero console errors (`verification/verify_a1_plain.png`) —
   breakage confined to the python-callable (LiteralLambdaVar) path, as claimed.
7. **Source-level cause**: `#6382` ("Move more globals to RegistrationContext",
   commit 7888170ad, in v0.9.9a1) removed the module-level `bundled_libraries` list
   from `reflex_base.components.dynamic` (present at module level in v0.9.8), which
   `reflex.components.dynamic` star re-exports. Not misuse: python-callable
   renderers/formatters are a designed rxe feature (rxe's own demo formatters.py and
   its error messages are built around it). A draft fix already exists in-repo on
   branch `origin/claude/reflex-enterprise-shim-mvevpt` (commit 5bda46ce8, "Restore
   `dynamic.bundled_libraries` as a deprecated shim"), corroborating that the fix is
   expected on the reflex/reflex-base side.

Attribution: primarily a **reflex 0.9.9a1 (reflex-base) breaking change** — a
module attribute that published reflex-enterprise releases (through 0.9.4) read at
runtime was removed without a deprecation shim; every published rxe is broken by it.
Secondary (pre-existing) reflex-base anomaly: CachedVarOperation/cached_property
converts internal AttributeErrors into misleading `VarAttributeError`s, which fully
masked the root cause here.

One env note for re-runners: do NOT override the ambient `NO_PROXY` when launching
`reflex run` in this environment — the ambient value whitelists
`registry.npmjs.org`; replacing it with only `localhost,127.0.0.1` sends bun through
the agent proxy and the frontend install dies with ~111 "ConnectionClosed
downloading package manifest" errors (observed twice; unrelated to this finding —
it happens after page compile, and the a1 crash happens before frontend install).

## VERIFICATION of finding 2 — AttributeError masking (independent, 2026-08-28, verifier agent 2)

Verdict: **CONFIRMED** — genuine reflex-base diagnosability defect; **NOT a regression**
(identical behavior reproduced on reflex-base 0.9.8), matching the claim. Attribution:
the masking itself is a **reflex (reflex-base) defect**, orthogonal to the enterprise
incompatibility of finding 1 (which it hid). Reproduced with the same PyPI venvs as the
finding-1 verification (`verification/../venv_a1`: reflex 0.9.9a1 + rxe 0.9.4;
`venv_098`: reflex 0.9.8 + rxe 0.9.4; both confirmed index installs, no direct_url).
Scripts + logs: `verification/masking/`.

1. **Pure reflex-base repro, no enterprise** (`probe_masking_pure.py`, run on BOTH
   versions -> `probe_masking_pure_{a1,098}.log`): a CachedVarOperation subclass declared
   exactly like reflex-base's own ConcatVarOperation whose `_cached_get_all_var_data`
   computation raises `AttributeError(MARKER)`. On 0.9.9a1 AND 0.9.8,
   `_get_all_var_data()` raises `VarAttributeError: Attribute _cached_get_all_var_data
   not found.` with `__cause__ is None` AND `__context__ is None`; MARKER appears nowhere
   in the traceback (CPython's `__getattr__` fallback clears the pending AttributeError
   before calling it, so even implicit exception context is destroyed — full masking,
   worse than a normal unchained raise). Same masking via the
   `str(var)` -> `_js_expr` -> `_cached_var_name` path.
2. **Specific to AttributeError** (control in the same probe): a `ValueError` raised at
   the identical spot propagates unmasked. So the descriptor-protocol +
   `CachedVarOperation.__getattr__` combination is the mechanism, as claimed.
3. **Organic repro on 0.9.9a1** (`probe_masking_rxe.py` -> `probe_masking_rxe_a1.log`):
   `LiteralVar.create([{"field": "x", "cellRenderer": lambda params: rx.text(...)}])`
   (the ag_grid column_defs shape) constructs lazily with no error; calling
   `._get_all_var_data()` on the LiteralArrayVar raises the masked VarAttributeError —
   no `__cause__`, no `__context__`, "bundled_libraries"/"reflex_enterprise" absent from
   the traceback. Matches the saved compile traceback
   (`artifacts/traceback_minimal_a1.txt`: base.py:2129 -> `__getattr__` 2121 -> raise at
   1472, no chained sections). Instrumenting `cached_property.__get__` (phase 2) captures
   the swallowed error and it is exactly the root cause of finding 1:
   `AttributeError: module 'reflex.components.dynamic' has no attribute
   'bundled_libraries'` — i.e. the information exists and is discarded.
4. **NEW, worse variant found while verifying** (phase 1b of `probe_masking_rxe.py`): on
   a Mapping-typed object var (bare dict column def -> LiteralObjectVar), the same
   underlying AttributeError does not raise AT ALL: `ObjectVar.__getattr__` treats
   `_cached_get_all_var_data` as JS item access and `_get_all_var_data()` **silently
   returns an ObjectItemOperation Var** (`{...}?.["_cached_get_all_var_data"]`) instead
   of VarData — silent wrong-value corruption, strictly worse than the misleading
   exception. Any fix should cover this path too (it lives in the same
   cached_property/__getattr__ interaction).
5. **Refutation attempts, all negative**: not an env quirk (deterministic CPython
   descriptor semantics, reproduced in fresh processes on 3.11.15); not app misuse
   (subclass declared exactly like reflex-base's own, and the organic path is designed
   rxe usage); not intentional — no code in the installed reflex_base relies on
   `hasattr`/`getattr` of `_cached_*` names, so catching-and-chaining inside
   `cached_property.__get__` would break nothing found; not fixed upstream — the current
   checkout (`packages/reflex-base/src/reflex_base/vars/base.py:2076`,
   `self._func(instance)` with no exception handling) still has the identical pattern.
6. Claimed line refs check out in installed 0.9.9a1: raise at base.py:1471-1472,
   `cached_property` at 1999 (`__get__` ~2052-2076), `CachedVarOperation.__getattr__`
   at 2105 (0.9.8: 1463 / 1991 / 2090 — same shape).

Severity **medium** agreed: no functional breakage by itself, but it converted this
release's headline enterprise breakage (finding 1) into an undebuggable one-liner, and
(per point 4) can silently corrupt VarData instead of erroring. Fix direction (catch
AttributeError in `cached_property.__get__` / the cached wrapper and re-raise chained as
a non-AttributeError) is sound and safe per point 5.

Rerun:
```bash
cd verification/masking
../..//venv_a1-or-your-own/bin/python probe_masking_pure.py   # any venv with reflex-base
CI=1 <venv_a1>/bin/python probe_masking_rxe.py                # needs rxe 0.9.4 + 0.9.9a1
```

## VERIFICATION of FINDING 3 (shipped-demo bundle path) — independent, 2026-08-28, second verifier

Verdict: **CONFIRMED, with one mechanism correction** — the shipped rxe ag_grid demo
is genuinely broken against reflex 0.9.8 (rxe-side incompatibility, NOT a 0.9.9a1
regression). Reproduced from scratch: fresh PyPI venv (`reflex==0.9.8`,
`reflex-base==0.9.8`, `reflex-enterprise==0.9.4`, Python 3.11), pristine copy of
`/home/user/reflex-enterprise/demos/ag_grid`, ports 3808/8808.
Artifacts: `verification_demo_bundle/` (phase logs, driver, screenshots).

Phases (each = one edit of `ag_grid/formatters.py` + full `CI=1 reflex run`):

- **A. Unmodified shipped demo** (`bundle_library("$/utils/components")` only):
  compile FAILS, exit 1, `ValueError: Library $/app_components/ag_grid/formatters
  is not bundled.` — exactly as claimed (`phaseA_shipped_098.log`). Confirmed the
  path is stale at the source level: on 0.9.8, `row_counter(...)`'s memo component
  reports `library == "$/app_components/ag_grid/formatters"` (mirrored memo layout,
  reflex #6457; per git tags that change shipped in reflex v0.9.6 already, so
  "stale since 0.9.6", not just 0.9.8 — the claim's ">=0.9.8" boundary is
  conservative but not wrong for what was tested).
- **B. Both paths bundled at IMPORT TIME ONLY — claim's intermediate state as
  literally written: REFUTED.** Compile still fails with the same ValueError
  (`phaseB_bothpaths_098.log`). Cause: `compile_app` calls
  `reset_bundled_libraries()` (confirmed at `reflex/compiler/compiler.py:1202` in
  the installed 0.9.8; it mutates the list in place, so the star-import alias in
  `reflex.components.dynamic` is reset too) after app import and before page
  compile, wiping ALL import-time `bundle_library()` calls. This is STRONGER than
  the claim's hedge: rxe's own error-message advice (module-level import-time
  `bundle_library`) simply does not work for page-compile validation on 0.9.8.
- **B'. Both paths bundled at import AND page-eval time**: compile PASSES,
  `.web/app/root.jsx` gets `import * as utils_components from "$/utils/components"`,
  and EVERY route returns HTTP 500 with vite `Internal server error: Cannot find
  module '$/utils/components' imported from .../root.jsx`
  (`phaseBprime_bothpaths_pageeval_098.log`; curl-verified on /, /formatters,
  /editable). So the claimed compile-pass/all-500 state exists, but only when the
  stale bundle survives to page-eval time.
- **C. Working fix** (drop stale path, bundle `$/app_components/ag_grid/formatters`
  at import + page-eval, identical to `demo_098/ag_grid/formatters.py`): compile
  passes, all 17 routes curl 200, and Chromium/Playwright on /formatters shows the
  Inline grid fully working — percent/flag/currency/scaled formatters render, memo
  row-counter button clicks to "1 (00:00)", zero non-license console errors
  (`shotsC_inline.png`, `drive_phaseC.py`).
- **c. Backend bundling desync: CONFIRMED and user-visible.** In the phase C run,
  first page load triggers `[Reflex Backend Exception]` — `hydrate`
  (reflex/state.py:2311) -> socketio delta encode -> rxe `serialize_lambda`
  (reflex_enterprise/vars.py:265) -> `ValueError: Library @radix-ui/themes is not
  bundled` (`phaseC_fixed_098.log` lines 243-354). The backend worker never runs
  `compile_app`, so the radix plugin's `bundle_library("@radix-ui/themes")`
  (compiler.py:1206-1208) never executes there. Consequences observed in the
  browser: the State tab's grid renders 0 cells (defs never reach the client) AND
  an error toast "ValueError: Library @radix-ui/themes is not bundled..." is shown
  to the user on the /formatters page (visible in `shotsC_inline.png`).

Attribution for a fix-agent: **reflex-enterprise 0.9.4 incompatibility with
reflex >= 0.9.8 (actually >= 0.9.6), not a reflex 0.9.9a1 defect** — three rxe-side
issues: (1) demo bundles the pre-mirroring memo path `$/utils/components`;
(2) rxe's `LiteralLambdaVar` error message recommends import-time `bundle_library`,
which `reset_bundled_libraries()` in `compile_app` makes ineffective for page
compile; (3) rxe validates bundling at runtime in the backend worker, whose
process state never includes compile-time plugin bundling, so state-var lambdas
fail to serialize (desync). Reflex-side follow-ups worth considering: the
compile-time reset semantics of user `bundle_library()` calls (2) and the
worker-side bundling state (3) are reflex-base lifecycle sharp edges that rxe (or
any downstream) can't robustly work around; neither is new in 0.9.9a1.

Rerun: `verification_demo_bundle/` logs name each phase; the exact formatters.py
edits per phase are described above (phase C's final state == `demo_098`'s file).
All verifier server/browser processes were killed after the runs.
