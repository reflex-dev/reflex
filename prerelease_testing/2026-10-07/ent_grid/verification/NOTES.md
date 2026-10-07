# Verification of H-1 (ent_grid §1a): State-var AG Grid `column_defs` render empty in prod on 0.10

Verifier: `verify_ent_grid_0`, 2026-10-07 12:37–13:40 UTC. Independent fixtures and driver, written before reading the
explorer's `apps/aggrid_min`, `apps/core_rerender` and `scripts/`; the explorer's repro was re-run only afterwards.

**Verdicts**
- **H-1: CONFIRMED** (and slightly NARROWED: only prerendered/static routes in prod; dynamic `[param]` routes, dev mode and
  client-side navigation are fine). Regression: yes — absent on 0.9.12 prod with the same wheel, present on 0.10.0a1 prod and 0.10.0a2 prod.
- **Claimed mechanism: CONFIRMED.** The trigger is the boot delta content (#7064 diff-against-compiled-defaults), NOT a moved
  `window.__reflex` assignment: the compiled `root.jsx` assigns `window.__reflex` in the same `ReflexProviders` `useEffect` on
  0.9.12, a1 and a2 (identical apart from a hash, `out/grep/root_jsx_diff.txt`).
- **New blast-radius finding:** Var-valued `detail_cell_renderer_params` (master/detail) is hit the same way: the expanded detail
  grid has NO columns on a2/a1 prod, works on 0.9.12 prod (s11).
- **Workaround claim CONFIRMED:** `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` fixes every grid case, but a page with a Python-lambda
  `cell_renderer` returning a Radix component (`rx.badge`) crashes with React #130 (s12) because `@radix-ui/themes` is moved to a lazy loader.

## Environment (PyPI + the offline wheel by file path; nothing from the checkouts)
Reused the existing venvs after `uv --no-config pip freeze` (all have greenlet 3.5.6, pydantic 2.13.5, the wheel
`reflex_enterprise-0.9.7a4` sha256 d9fdd6a5…7647 installed `@ file://…/enterprise_wheel/…whl`):

| venv | reflex / reflex-base / components-core | used for |
|---|---|---|
| `alpha2-ent` | 0.10.0a2 / 0.10.0a2 / 0.10.0a2 + wheel[mcp] | entv a2 prod/dev/lazy, explorer aggrid_min |
| `ent_grid-a1` | 0.10.0a1 / 0.10.0a1 / 0.10.0a1 + wheel (sqlalchemy 2.0.54) | entv a1 prod |
| `ent_grid-s912` | 0.9.12 / 0.9.12 / 0.9.10.post1 + wheel | entv 0.9.12 prod |
| `alpha2` (no enterprise) | 0.10.0a2 | corev a2 prod/dev, explorer core_rerender |
| `alpha` (no enterprise) | 0.10.0a1 | corev a1 prod |
| `stable` (no enterprise) | 0.9.12 | corev 0.9.12 prod |

No new venv was created (so no greenlet note needed beyond: all reused venvs already contain greenlet).
Server env: `CI=true REFLEX_TELEMETRY_ENABLED=false VERIFY_BACKEND_PORT=<bp>` (+ `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` for the
lazy run); proxy-bypass variables only on the driver side. Ports: prod single port 3680–3691, dev 3681/8681 and 3686/8686.
One server at a time; every run stopped with `bin/stop.sh` (process-group kill + check that 3680–3699/8680–8699 are free).

## Fixtures (`apps/`)
- `apps/probe.py` (copied into each app package): `ReflexProbe`, an `rx.Component` with inline `_get_custom_code`. On EVERY render
  it pushes `{label, n, has: typeof window.__reflex !== 'undefined', t: performance.now()}` into `window.__trace` and renders
  `<label>|HAS_REFLEX|<json>` or `<label>|NO_REFLEX|<json>` (no counter in the DOM, so prerendered HTML == first client render).
- `apps/corev` (core only, no enterprise import): `/` (on_load = `Touched.on_load_set`) with probes on `Untouched.cols`,
  `Untouched.n` (never changed at boot), `Touched.value` (changed by on_load), `Other.x` (changed by a button), a literal-prop probe;
  `/second` (probe on `Untouched.cols` + link to `/`); `/dyn` (a `@rx.var -> rx.Component` dynamic component + probe).
- `apps/entv` (enterprise): `/` grid `w_state` (`column_defs=GridState.cols`), grid `w_literal` (literal `column_defs`), probes,
  buttons "bump other" (`OtherState`) / "bump gridstate" (`GridState.clicks`); `/other`; `/memo` (two `@rx.memo` grids: column defs as
  a memo prop, and read from State inside the memo); `/onload` (`LoadState` grid changed by on_load + `GridState` grid);
  `/detail` (master/detail, literal outer columns, `detail_cell_renderer_params=DetailState.params` vs a literal dict);
  `/renderer` (literal columns with a Python-lambda `cell_renderer` returning `rx.badge`); `/item/[pid]` (dynamic route, not prerendered).
- `drivers/drive.py`: Playwright (driver venv, asserts `sys.executable` is the driver venv and that the listening process runs from
  the expected venv). An init script (1) traps `window.__reflex` with a setter that records `performance.now()` and the JS stack,
  (2) subclasses `WebSocket` to log every `/_event` frame with in-page timestamps, (3) polls `.ag-header-cell` / `.ag-cell` counts of
  each grid wrapper every 50 ms. Each scenario writes `<scenario>.json` (measure at boot+3 s and again +4 s, timeline, parsed boot
  frames, raw frames, console, page errors) and a screenshot (`.jpg` here; PNG in the scratch dir).
- `drivers/summarize.py out > out/SUMMARY.md` builds the tables below.

## Rerun
```
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_grid_0          # copy apps/entv, apps/corev (+ apps/probe.py into the package) to $W/runs/<name>
cd $W
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drivers/drive.py"
# enterprise, prod (single port):
bin/start.sh alpha2-ent    $W/runs/entv_a2   logs/entv-a2-prod.log   prod 3680 3680 && $DRV --app entv --url http://localhost:3680 --out out/entv_a2_prod   --server-venv alpha2-ent;    bin/stop.sh
bin/start.sh ent_grid-a1   $W/runs/entv_a1   logs/entv-a1-prod.log   prod 3682 3682 && $DRV --app entv --url http://localhost:3682 --out out/entv_a1_prod   --server-venv ent_grid-a1;   bin/stop.sh
bin/start.sh ent_grid-s912 $W/runs/entv_s912 logs/entv-s912-prod.log prod 3683 3683 && $DRV --app entv --url http://localhost:3683 --out out/entv_s912_prod --server-venv ent_grid-s912; bin/stop.sh
bin/start.sh alpha2-ent    $W/runs/entv_a2lazy logs/entv-a2-prod-lazyflag.log prod 3684 3684 REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true && $DRV --app entv --url http://localhost:3684 --out out/entv_a2_prod_lazyflag --server-venv alpha2-ent; bin/stop.sh
# enterprise, dev:
bin/start.sh alpha2-ent    $W/runs/entv_a2dev logs/entv-a2-dev.log dev 3681 8681 && $DRV --app entv --url http://localhost:3681 --backend-port 8681 --out out/entv_a2_dev --server-venv alpha2-ent; bin/stop.sh
# core only:
bin/start.sh alpha2 $W/runs/corev_a2   logs/corev-a2-prod.log   prod 3685 3685 && $DRV --app corev --url http://localhost:3685 --out out/corev_a2_prod   --server-venv alpha2; bin/stop.sh
bin/start.sh alpha  $W/runs/corev_a1   logs/corev-a1-prod.log   prod 3687 3687 && $DRV --app corev --url http://localhost:3687 --out out/corev_a1_prod   --server-venv alpha;  bin/stop.sh
bin/start.sh stable $W/runs/corev_s912 logs/corev-s912-prod.log prod 3688 3688 && $DRV --app corev --url http://localhost:3688 --out out/corev_s912_prod --server-venv stable; bin/stop.sh
bin/start.sh alpha2 $W/runs/corev_a2dev logs/corev-a2-dev.log dev 3686 8686 && $DRV --app corev --url http://localhost:3686 --backend-port 8686 --out out/corev_a2_dev --server-venv alpha2 --only c1,c7; bin/stop.sh
# subsets: --only s1,s6,s7,s8,s9,s10,s11,s12,s13 (entv) / c1,c6,c7,c8 (corev); s1 runs s1-s5 in one context, c1 runs c1-c5.
$SB/envs/driver/bin/python drivers/summarize.py out > out/SUMMARY.md
```
(`/detail`, `/renderer`, `/item/[pid]` and `/dyn` were added after the first a2/s912/a1 passes and run with `--only s11,s12` /
`s13` / `c8` against rebuilt servers — logs `*-prod-2.log`, `*-prod-3.log`.)

## Results — enterprise (`out/SUMMARY.md` has the full matrix incl. probe render counts)
Counts are `.ag-header-cell` / `.ag-cell` inside the grid wrapper, 4 s after the boot frames settled (unchanged vs the boot+3 s measure).

| scenario | 0.9.12 prod + wheel | a1 prod + wheel | a2 prod + wheel | a2 dev | a2 prod + lazy flag |
|---|---|---|---|---|---|
| s1 full load: state grid / literal grid | 2h6c / 2h6c | **0h0c** / 2h6c | **0h0c** / 2h6c | 2h6c / 2h6c | 2h6c / 2h6c |
| s2 reload | ok | **empty** | **empty** | ok | ok |
| s3 after an unrelated event (other substate) | ok | **empty** | **empty** | ok | ok |
| s4 after an event on the SAME substate | ok | recovers | recovers | ok | ok |
| s5 reload after s4 (substate now differs from default) | ok | ok | ok | ok | ok |
| s6 full load `/other` → client nav to `/` | ok | ok | ok | ok | ok |
| s7 full load `/` → `/other` → back (client nav) | ok | ok | ok | ok | ok |
| s8 `/memo`: memo prop grid / State-inside-memo grid | ok / ok | **empty / empty** | **empty / empty** | ok | ok |
| s9 `/onload`: on_load-changed substate / unchanged GridState on same page | ok / ok | ok / **empty** | ok / **empty** | ok | ok |
| s10 full load, second fresh context | ok | **empty** | **empty** | ok | ok |
| s11 `/detail` expand row: detail grid headers, state params / literal params | Count,Value / Count,Value | **[] / Count,Value** | **[] / Count,Value** | — | Count,Value / Count,Value |
| s12 `/renderer` lambda `cell_renderer` → `rx.badge` | 3 badges | 3 badges | 3 badges | — | **page crash, React #130** |
| s13 `/item/1` dynamic (non-prerendered) route | — | — | ok (probe renders once, already HAS_REFLEX) | — | — |

Screenshots: `out/entv_a2_prod/s2_reload.jpg` (empty state grid above a populated literal grid), `out/entv_s912_prod/s2_reload.jpg`,
`out/entv_a2_prod/s11_detail_expand.jpg` (empty detail header), `out/entv_a2_prod_lazyflag/s12_renderer_full_load.jpg` (#130 error page).
The lazy-flag runs also show `Minified React error #418` (hydration text mismatch) on pages containing MY probe only: with the flag
`window.__reflex` exists at the first client render, so the probe text differs from the prerendered HTML. Pages without the probe
(`/memo`, `/onload`, `/detail`) have no #418, i.e. the AG Grid formatter itself does not cause a hydration mismatch.

## Results — core only (no enterprise): probe state after boot (render count in parentheses)
| scenario | 0.9.12 prod | a1 prod | a2 prod | a2 dev |
|---|---|---|---|---|
| c1 full load: Untouched / Touched(on_load) / Other / literal-prop | HAS(2) / HAS(3) / HAS(2) / **NO(1)** | **NO(1)** / HAS(2) / **NO(1)** / NO(1) | **NO(1)** / HAS(2) / **NO(1)** / NO(1) | HAS(2) / HAS(2) / HAS(2) / HAS(2) (StrictMode double render) |
| c2 reload | same as c1 | same as c1 | same as c1 | all HAS |
| c3 after `Other.bump` | Untouched HAS | Untouched NO, Other HAS | Untouched NO, Other HAS | all HAS |
| c4 after `Untouched.bump` | HAS | Untouched HAS(2) | Untouched HAS(2) | HAS |
| c5 reload after c4 | HAS | HAS (delta now carries untouched+other) | HAS | HAS |
| c6 `/second` full load → client nav to `/` | HAS everywhere (incl. literal) | same | same | — |
| c8 `/dyn` dynamic component (`@rx.var -> rx.Component`) | — | — | renders `dynamic-ok` although its substate is not re-rendered (probe NO(1)) | — |

The literal-prop probe (no state dependency) is NO_REFLEX after every prod full load on ALL versions including 0.9.12: the
render-before-`window.__reflex` ordering is pre-existing; 0.9.12 only masked it for state consumers.

## Mechanism evidence
1. WHERE/WHEN `window.__reflex` is assigned — setter trap stack: prod a2 `assets/root-*.js:82:324`, prod 0.9.12 `assets/root-*.js:82:324`,
   dev a2 `app/root.jsx:27:21` = the `useEffect` in `ReflexProviders` (compiled `.web/app/root.jsx:25-35`, same on all three versions;
   template `reflex_base/compiler/templates.py:214` in both 0.9.12 and 0.10.0a2 site-packages). With the lazy flag it is module scope
   (`templates.py:226-231`; compiled `.web/app/root.jsx:21-26` of `runs/entv_a2lazy`).
2. Timeline, enterprise `/` full load (a2 prod, `out/entv_a2_prod/s1_full_load.json`): probe render #1 NO_REFLEX at 206 ms →
   boot `hydrate_and_load` sent in the socket.io connect auth at 240.6 ms → `window.__reflex` assigned at 241.1 ms → literal grid
   gets 2 headers at 324.7 ms → deltas at 329.5/330.1 ms carry ONLY `reflex___state____state` → state grid stays 0/0 forever.
   0.9.12 prod (`out/entv_s912_prod/s1_full_load.json`): probe #1 NO_REFLEX 185.9 ms → `__reflex` 239.8 ms → `hydrate` +
   `on_load_internal` sent 339 ms → delta at 342.1 ms carries ALL 8 substates (incl. `grid_state`, `other_state`, `load_state`) →
   probe #2 HAS_REFLEX at 343.2 ms → state grid 2/6 at 375 ms.
3. Boot frames (core app): 0.9.12 first delta = every substate (`corev___corev____untouched`, `other`, `touched`, internal states);
   a1 and a2 deltas = root state + `touched` only (the substate on_load changed). `applyDelta` (`state.js:275` a2 / `:160` 0.9.12) always
   returns a new object, so a substate present in a delta re-renders its consumers; an absent one never does.
4. Backend: `reflex/state.py:2338 hydrate_and_load` → `:2377 _diff_against_initial_state` (`:2490-2541`) drops unchanged vars and
   omits a substate entirely when nothing changed (`if changed: diff[state_name] = changed`); the frontend sends the hashes on the
   first connect only (`reflex_base/.templates/web/utils/state.js:703-728 bootAuth(true)`), which is why a reload after the substate
   diverged from its defaults (s5/c5) and client-side navigation (page mounts after the effect ran) recover.
5. Why dev and dynamic routes are fine: the route component's first render happens after `ReflexProviders` mounted (dev: route
   module loaded asynchronously; prod dynamic route: SPA fallback / HydrateFallback first), so `window.__reflex` already exists
   (dev probe render #1 at 1513 ms vs `__reflex` at 1488 ms; s13 probe renders once, HAS_REFLEX).
6. Enterprise trigger: `reflex_enterprise/components/ag_grid/aggrid.py:457` compiles a Var `column_defs` to
   `formatColumnDefs(<var>)` at render; `aggrid.py:2286-2290` returns `[]` when `typeof __reflex === 'undefined'`; `utils.py:30` does the
   same for Var `detail_cell_renderer_params` (`formatDetailCellRendererParams` → nested `detailGridOptions.columnDefs` →
   `formatColumnDefs`, `aggrid.py:2300-2311`). Literal `column_defs` are converted in Python (`aggrid.py:445-455`) and never call it.
   In the compiled module the `jsx`/`Fragment` locals that the guard protects are not visible to `createParamsFormatter`'s `eval`
   (sibling closure, `out/grep/compiled_enterprise_excerpts.txt`), so the guard looks removable.

## Blast radius (`out/grep/`)
- Published reflex / reflex-base / reflex-components-* (a2 and 0.9.12 site-packages): `__reflex` is only read in
  `reflex_base/components/dynamic.py` (dynamic components: evaluated in a `useEffect` after `await window.__reflex_load?.()` — c8 shows
  they are NOT affected) and `state.js evalReactComponent` (same path). No reflex-components-* package references it.
- reflex-enterprise wheel: `aggrid.py` (`formatColumnDefs` and everything that nests it: Var `column_defs`, Var
  `detail_cell_renderer_params`/detail grid options — AFFECTED) and `vars.py:174` (Python-lambda cell renderers etc. read
  `__reflex[...]` inside the generated function body, at cell-render time — NOT affected in default mode, s12 passes; BROKEN with the
  lazy flag for libraries moved to the lazy loader). No other enterprise component (map, dnd, flow, mantine) references `__reflex`.
- User-visible: on prerendered pages in prod, AG Grids whose `column_defs` or `detail_cell_renderer_params` come from a State var
  (including `@rx.memo` grids and `rx.ComponentState` grids, per the explorer) show no header/cells — on first load, reload and in
  any new tab — until a var of that same substate changes. It is not cosmetic: the grid has no columns at all. A grid fed from a
  substate that the session already modified (or on_load modifies) works, which makes it look intermittent.
- Generic: any user custom code / `rx.Var` expression that reads `window.__reflex` (or any other global populated in a passive
  effect) during render and consumes an unchanged substate. Non-state render-time readers are broken in prod on every version (pre-existing).

## Re-run of the explorer's written repro (after my own fixtures)
`apps/aggrid_min` + `scripts/probe_aggrid_min.py` and `apps/core_rerender` + `scripts/probe_core_rerender.py`, copied to
`$W/runs/explorer_*` and `$W/explorer_rerun/scripts`, run on MY ports (3690/3691) instead of the documented 3309/3305:
both reproduce on a2 prod (`out/explorer_rerun/aggrid_min_a2`: state grid checks fail on load and reload, literal grid passes;
`out/explorer_rerun/core_rerender_a2`: untouched probe stays NO_REFLEX). Repro-quality notes: the explorer's guard
(`qa_common.assert_driver_and_server`) hard-codes `$SB/apps/ent_grid/pids/current.pid` written by its own `start_server.sh`, so a
stranger cannot run the probes against their own server without a one-line patch (done in the copy: pid path → my pgid file);
the documented ports are the explorer's range. Otherwise the NOTES were sufficient.

## Judgement
- Release blocker for 0.10.0: **yes (high)**, for the enterprise train. AG Grid with State-held column defs is the documented
  pattern (the enterprise demo's own `/master-detail` page does it) and prod is where users run; no error is logged, the grid is
  simply empty, and the only workaround flag breaks other grid features.
- Where to fix: primarily in **reflex** — make `window.__reflex` available before the first render in the default path, as the
  lazy path already does (`templates.py:226-231`, module-scope assignment guarded by `typeof window`), which also fixes the
  pre-existing non-state reader case; re-sending every substate on boot would undo #7064's measured win and only re-mask the
  ordering bug. Defence in depth in **reflex-enterprise**: drop the render-time `typeof __reflex` guard in `formatColumnDefs`
  (only SSR needs the `typeof window` part) so the grid does not depend on reflex's effect ordering — a wheel already in users'
  hands (0.9.7a4 and earlier) will otherwise stay broken against reflex 0.10 until reflex changes.
- Hydration caveat for the reflex fix: a component whose render output depends on `__reflex` will then differ from the prerendered
  HTML (my probe triggers React #418 under the lazy flag); the AG Grid path did not (no #418 on probe-free pages).

## Noise (benign)
`/favicon.ico` 404 on every app; AG Grid Enterprise "License Key Not Found" console banners on pages that load enterprise modules;
`DeprecationWarning: Passing strings to disable_plugins` and implicit Radix enablement in the server log.

## Not covered
Redis state manager (the diff path is the same code; not run). Granian vs uvicorn worker differences (all prod runs used
reflex's default granian). The explorer's full `ag_grid` demo was not re-run (my fixture + its minimal repro were enough).
