# a3_ent_grid — N-025 re-verification on reflex 0.10.0a3 + reflex-enterprise 0.9.7a5, enterprise#273 regression hunt

Agent `a3_ent_grid`, 2026-10-07 19:39 UTC on. Ports 3300-3319 (prod single port / dev frontend) and 8300-8319 (dev backend).
Work dir `$SB/apps/a3_ent_grid` (`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`).
Everything installs from PyPI + the offline enterprise wheels by file path (shared read-only venvs, nothing installed by this agent).

STATUS: in progress (this file is updated after every sub-test; see "Results so far").

## Venvs used (shared, read-only; versions printed by `bin/vers.py` at every server start and checked by the driver)
| venv | reflex / reflex-base | reflex-enterprise | role |
|---|---|---|---|
| `a3-ent` | 0.10.0a3 / 0.10.0a3 (components-core 0.10.0a2, sqlalchemy 2.1.4, greenlet 3.5.6) | 0.9.7a5 offline wheel | under test |
| `a3-ent-a4` | 0.10.0a3 / 0.10.0a3 | 0.9.7a4 offline wheel | user upgrades reflex but not enterprise |
| `alpha2-ent` | 0.10.0a2 / 0.10.0a2 | 0.9.7a4 | positive control (the a2-pass state) |
| `alpha2-ent-a5` | 0.10.0a2 / 0.10.0a2 | 0.9.7a5 | enterprise fix alone on reflex a2 |
| `s912-ent-a5` | 0.9.12 / 0.9.12 (components-core 0.9.10.post1) | 0.9.7a5 | a5 must not break 0.9.12 |
| `driver` | playwright (Chromium `/opt/pw-browsers/chromium`) | | drivers |

## Layout (`$SB/apps/a3_ent_grid` = this directory's source of truth)
- `apps/entv`, `apps/corev`, `apps/probe.py` — the a2-pass verifier fixtures (`../../2026-10-07/ent_grid/verification/apps`), unchanged
  except `rxconfig.py`: default backend port 8300 and a guard asserting `reflex` imports from `$SB/envs/$VERIFY_VENV/`.
- `apps/aggrid_min` — the explorer's minimal repro (`../../2026-10-07/ent_grid/apps/aggrid_min`), + the same venv guard.
- `apps/entr` — NEW regression-hunt fixture for enterprise#273 (see §3).
- `drivers/drive.py` — the verifier's driver (traps the `window.__reflex` setter, logs `/_event` frames, polls grid header/cell
  counts every 50 ms) + a3_ent_grid additions: `--app entr` scenarios r1-r5, badge counts in the poll, per-grid
  badges/memo badges/tooltip texts/pinned rows/group rows/`.cheap` cells/row texts in the measure, `cell_render` trace
  events (whether `window.__reflex` existed when AG Grid invoked a renderer), HTTP >= 400 / failed requests, and the
  server venv's package versions in `server_check.json`.
- `drivers/summarize.py out [runs...]` (entv/corev tables), `drivers/anomalies.py out/<run>...` (page errors, non-benign console,
  `__reflex` time vs first grid headers, trace cell renders), `drivers/grids.py out/<run>` (entr grid contents).
- `scripts/probe_aggrid_min.py` + `scripts/qa_common.py` — explorer's probe; guard patched to read `pids/current.pgid`.
- `bin/start.sh <venv> <app-dir> <log> prod|dev <fp> <bp> [ENV=..]`, `bin/stop.sh` (process-group kill + port check),
  `bin/run.sh <venv> <app> prod|dev <port> <out-name> [driver args] [-- ENV=..]` (refresh `runs/<app>_<venv>` from `apps/`, start,
  drive, stop; dev backend = port+5000), `bin/sync_dest.sh` (copy to DEST), `bin/vers.py`.

## Rerun (from `$SB/apps/a3_ent_grid`, after copying this directory's `apps/` to `src/`)
```
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_ent_grid; cd $W
# N-025 matrix (entv s1-s13; s1 runs s1-s5 in one context)
bin/run.sh alpha2-ent    entv prod 3300 entv_alpha2ent_prod --only s1,s11      # positive control: must stay broken
bin/run.sh alpha2-ent-a5 entv prod 3301 entv_alpha2enta5_prod
bin/run.sh alpha2-ent-a5 entv dev  3302 entv_alpha2enta5_dev
bin/run.sh s912-ent-a5   entv prod 3303 entv_s912enta5_prod
bin/run.sh a3-ent        entv prod 3306 entv_a3ent_prod
bin/run.sh a3-ent        entv dev  3307 entv_a3ent_dev
bin/run.sh a3-ent-a4     entv prod 3308 entv_a3enta4_prod --only s1,s11,s8
bin/run.sh a3-ent        aggrid_min prod 3309 aggrid_min_a3ent_prod           # explorer's probe
bin/run.sh a3-ent-a4     aggrid_min prod 3310 aggrid_min_a3enta4_prod
$SB/envs/driver/bin/python drivers/summarize.py out > out/SUMMARY.md
$SB/envs/driver/bin/python drivers/anomalies.py out/entv_a3ent_prod
# regression hunt (entr r1-r5)
bin/run.sh alpha2-ent-a5 entr dev  3304 entr_alpha2enta5_dev
bin/run.sh alpha2-ent-a5 entr prod 3305 entr_alpha2enta5_prod
$SB/envs/driver/bin/python drivers/grids.py out/entr_alpha2enta5_prod
```
(The a2-pass verifier ran the first positive-control server with `bin/start.sh` + `drivers/drive.py` directly; `run.sh` does the same.)

## Results so far

### 1. N-025 (entv fixture; `.ag-header-cell`/`.ag-cell` counts inside the grid wrapper 4 s after the boot frames)
| scenario | a2-pass a2+a4 prod | alpha2-ent (a2+a4) prod, control | alpha2-ent-a5 prod | alpha2-ent-a5 dev | s912-ent-a5 prod | **a3-ent prod** | **a3-ent dev** | a3-ent-a4 prod |
|---|---|---|---|---|---|---|---|---|
| s1 full load state / literal grid | 0h0c / 2h6c | 0h0c / 2h6c | 2h6c / 2h6c | 2h6c / 2h6c | 2h6c / 2h6c | **2h6c / 2h6c** | 2h6c / 2h6c | **0h0c** / 2h6c |
| s2 reload | empty | empty | ok | ok | ok | **ok** | ok | **empty** |
| s3 after unrelated-substate event | empty | empty | ok | ok | ok | **ok** | ok | **empty** |
| s4 after same-substate event | recovers | recovers | ok | ok | ok | ok | ok | recovers |
| s5 reload after s4 | ok | ok | ok | ok | ok | ok | ok | ok |
| s6 `/other` → client nav `/` | ok | — | ok | ok | ok | ok | ok | — |
| s7 `/` → `/other` → back | ok | — | ok | ok | ok | ok | ok | — |
| s8 `/memo` memo-prop / State-in-memo grid | empty / empty | — | ok / ok | ok / ok | ok / ok | **ok / ok** | ok / ok | **empty / empty** |
| s9 `/onload` on_load-changed / unchanged grid | ok / empty | — | ok / ok | ok / ok | ok / ok | **ok / ok** | ok / ok | — |
| s10 second fresh context | empty | — | ok | ok | ok | **ok** | ok | — |
| s11 `/detail` detail-grid headers state / literal params | `[]` / Count,Value | `[]` / Count,Value | Count,Value ×2 | Count,Value ×2 | Count,Value ×2 | **Count,Value ×2** | Count,Value ×2 | **`[]`** / Count,Value |
| s12 `/renderer` lambda `rx.badge` | 3 badges | — | 3 | 3 | 3 | 3 | 3 | — |
| s13 `/item/1` dynamic route | ok | — | ok | ok | ok | ok | ok | — |

Explorer's `aggrid_min` probe: a3-ent prod 4/4 PASS (State grid `Make, Price` on load and reload); a3-ent-a4 prod 2/4 — State
grid `[]` on load and reload (exactly the a2-pass failure).
Page errors: 0 in every run; non-benign console: none (only `/favicon.ico` 404 — not reported by Playwright's response
events, i.e. the browser's favicon fetch — and the AG Grid licence banners). Server logs: no tracebacks; the dev logs end
with `[ERROR] Unexpected exit from worker-1` because `bin/stop.sh` SIGTERMs the whole process group (same on a2; harness artefact).
Boot frames on a3 are unchanged from a2: `hydrate_and_load` in the socket.io connect auth, deltas carry only the root state;
`window.__reflex` is still assigned in the ReflexProviders effect (s1 a3-ent prod: 350 ms) — the fix is entirely enterprise-side.
Grid headers appear ~100 ms after the `__reflex` assignment in every prod run (a5 formats on the first render; AG Grid itself
paints its header/cells after its own effects).

**Verdict N-025: FIXED with reflex 0.10.0a3 + reflex-enterprise 0.9.7a5 (prod and dev); NOT fixed for a user who upgrades reflex
to a3 but keeps enterprise 0.9.7a4 (a3-ent-a4 prod identical to the a2-pass failure) — users must upgrade enterprise too.
The enterprise fix alone already fixes reflex 0.10.0a2 (alpha2-ent-a5), and a5 keeps 0.9.12 working (s912-ent-a5).**

### 3. enterprise#273 regression hunt (`apps/entr`, every grid on a prerendered static route)
Pages: `/lit` (literal column defs: lambda `rx.badge` renderer + `tooltip_field`/`header_tooltip`, lambda `value_formatter`,
lambda `value_getter`, `cell_class_rules`, lambda `rx.tooltip(rx.text)` renderer, lambda → `@rx.memo` component (the demo's
documented `bundle_library(memo)` pattern), Python trace renderer; pinned top row; literal row grouping), `/var` (State var with
JS-string expressions incl. an arrow-function trace renderer, `{function}` getter, arrow getter, pinned row from State;
State var whose DEFAULT holds the same Python lambdas; `rx.cond(State.flag, <lambda cols>, <plain>)`; computed-var column
defs; State row grouping), `/detail2` (master/detail: literal detail params with lambda `rx.badge` + trace renderer in the detail
grid; State detail params with JS-string renderer/formatter), `/memo2` (`@rx.memo` grid fed the lambda-holding State var).
Note: `rx.cond` branches containing Python lambdas need `dynamic.bundle_library("@radix-ui/themes")` at import (enterprise raises
`Library @radix-ui/themes is not bundled ...` otherwise, and says so) — documented behaviour, not a5-specific.

| run | r1 /lit load+reload | r2 /var load, reload, toggle cond, bump | r3 /detail2 expand (load + reload) | r4 /memo2 | r5 client nav | trace renders without `__reflex` | page errors |
|---|---|---|---|---|---|---|---|
| alpha2-ent-a5 dev | all grids full | all grids full, cond toggles 6↔1 cols | detail Count,Value ×2, 2 badges | 6h/18c, 6 badges | ok | 0 / 74 | 0 |
| alpha2-ent-a5 prod | all grids full | same | same | same | ok | 0 / 37 | 0 |
Values checked in the DOM (prod): `$1`, `double=2`, `memo:Tesla`, `T:Tesla`, `S:Tesla`, `TESLA`, `1 EUR`, pinned `PINNED | $99 | 198`,
group `US (2)`/`sum`, one `.cheap` cell. Every renderer invocation happened AFTER `window.__reflex` was assigned (first trace
cell render 352 ms vs `__reflex` 241 ms on `/lit` prod).
Quirk (to baseline on 0.9.12): `rx.badge(params.value)` shows the value JSON-quoted (`"Tesla"`).
AG Grid dev warning `#306 tooltipField is deprecated` (my fixture uses `tooltip_field`; AG Grid 36.2 deprecation, dev only).
