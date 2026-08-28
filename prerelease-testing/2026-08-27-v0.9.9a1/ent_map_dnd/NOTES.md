# ent_map_dnd — reflex-enterprise 0.9.4 map + dnd demos on reflex 0.9.9a1

Cluster: `ent_map_dnd`. Tested 2026-08-28 against PyPI packages only:
`reflex==0.9.9a1` + `reflex-enterprise==0.9.4` (venv099a1) vs baseline
`reflex==0.9.8` + `reflex-enterprise==0.9.4` (venv098), Python 3.11.
Demo sources copied unmodified from `/home/user/reflex-enterprise/demos/{map,dnd}`
(that checkout was used as read-only reference only; nothing was installed from it).

## TL;DR

- **Both demos work end-to-end on 0.9.9a1, identically to 0.9.8**: map 13/13
  Playwright checks, dnd 18/18 (dev mode). Prod mode could not be tested on
  EITHER version: reflex-enterprise gates `reflex run --env prod` behind a paid
  subscription (see anomaly 5).
- **FINDING-001 does NOT fire for the shipped map/dnd demos** — but it is real and
  one lambda away: `repro_finding001_dnd_can_drop.py` shows the exact
  `AttributeError: module 'reflex.components.dynamic' has no attribute
  'bundled_libraries'` (reflex_enterprise/vars.py:143) for a `can_drop` lambda that
  uses the documented `bundle_library()` pattern. Works on 0.9.8, crashes on
  0.9.9a1 → regression (in the reflex-base/enterprise contract, not in demo code).
- Precise trigger conditions mapped below (why the demos escape).

## Why the shipped demos do NOT hit FINDING-001

`LiteralLambdaVar.create` (reflex_enterprise/vars.py) calls
`_validate_and_extend_return_expr` — the only reader of
`reflex.components.dynamic.bundled_libraries` — **only when
`not is_static(func)`**, and the crashing line 143 is only reached when the
lambda's compiled return expression carries VarData **without hooks** (a
state-var reference raises the "cannot use hooks" ValueError at line 138 first,
on both 0.9.8 and 0.9.9a1 equally).

- **map demo**: no LambdaVar-typed props anywhere (`grep LambdaVar` in the wheel:
  only `components/dnd/dnd.py` uses it). The `on_click=lambda e: my_api.set_view(...)`
  is a normal reflex event-trigger lambda, not a LambdaVar. → unaffected.
- **dnd demo**: `basic`/`foreach` pass no `can_drop`/`can_drag`; `kanban`'s
  `_can_drop` functions are decorated `@rxe.static` → validation skipped; the
  DropTarget/Draggable `collect` functions in the wheel are `@static` too.
  → unaffected.
- **Who IS affected** (dnd cluster): any user passing a plain (non-`@rxe.static`)
  function to `rxe.dnd.drop_target(can_drop=...)` / `draggable(can_drag=...)`
  (or any LambdaVar prop) whose return expression carries imports via the
  officially supported `bundle_library()` mechanism — the exact feature this
  validator implements. Crashes at component construction (page definition)
  time on 0.9.9a1. ag-grid value formatters are the higher-traffic route
  (other cluster).

Repro: `repro_finding001_dnd_can_drop.py` — run with each venv's python from the
cluster dir. 0.9.8 → exit 0 ("OK: drop_target ... created"); 0.9.9a1 → exit 1
with the full traceback ending at
`reflex_enterprise/vars.py:143  bundled_libraries = set(dynamic.bundled_libraries)`.
Logs: `logs/repro_finding001_099a1.log`, `logs/repro_finding001_098.log`.

## Setup / how to rerun

```
SB=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad
D=$SB/apps/ent_map_dnd          # contains map/, dnd/, drivers/, repro script
uv venv $D/venv099a1 --python 3.11
uv pip install --python $D/venv099a1/bin/python --prerelease=allow 'reflex==0.9.9a1' 'reflex-enterprise==0.9.4'
uv venv $D/venv098 --python 3.11
uv pip install --python $D/venv098/bin/python 'reflex==0.9.8' 'reflex-enterprise==0.9.4'
# provenance check (run from $D, NOT from a dir containing a reflex checkout):
cd $D && ./venv099a1/bin/python -c "import reflex_enterprise, reflex; print(reflex_enterprise.__file__, reflex.__file__)"
```

**IMPORTANT — `CI=1` is required.** `rxe.App` exits at startup with
"`reflex-enterprise` is free to use but you must be logged in." unless a Reflex
access token is configured. `AppEnterprise._check_login` skips the gate when the
`CI` env var is set (or `REFLEX_BACKEND_ONLY`). All runs below use `CI=1`.
Side note: on 0.9.9a1 the login-failure path itself emits
`DeprecationWarning: console.error has been deprecated in version 0.9.9 ...
(reflex_enterprise/app.py:120)` before exiting — enterprise 0.9.4 still calls the
now-deprecated `console.error` (see `logs/map_099a1_run1.log`).

Run servers (one at a time; ports from this cluster's reserved ranges):

```
cd $D/map && CI=1 REFLEX_TELEMETRY_ENABLED=false $D/venv099a1/bin/reflex run \
    --frontend-port 3340 --backend-port 8340 --loglevel debug > $D/logs/map_099a1.log 2>&1 &
# dnd: same with $D/dnd, ports 3341/8341
# 0.9.8 baseline: venv098, map 3342/8342, dnd 3343/8343 (rm -rf .web .states reflex.lock first)
# prod: add --env prod with frontend-port == backend-port; exits at the enterprise
#       paid-subscription gate on both versions (see anomaly 5)
```

Poll `http://localhost:<FP>/` until 200 (first run does a bun install, 1-3 min),
then drive (drivers need playwright; `$SB/envs/driver/bin/python`, Chromium at
`/opt/pw-browsers/chromium`):

```
cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drivers/drive_map.py http://localhost:3340 $D/shots/map_099a1 map_099a1
  $SB/envs/driver/bin/python drivers/drive_dnd.py http://localhost:3341 $D/shots/dnd_099a1 dnd_099a1
```

Drivers print one `RESULT PASS/FAIL <check>` line per check plus console /
network-failure / page-error summaries, write screenshots + `capture.json`
(all console messages, failed requests) into the shots dir, and exit non-zero on
any FAIL.

## What was tested (all Playwright, real Chromium, real mouse)

### map demo (leaflet) — 13/13 PASS on 0.9.9a1, 13/13 on 0.9.8

- index renders demo cards
- `/map-controls`: map renders; zoom control topright, scale bottomleft,
  attribution topleft (all non-default positions honored)
- `/fly-to-location`: 2 markers; tooltip "Baz bum" on hover; popup on click with
  a working button (`rx.toast` fires from inside leaflet popup); mouse-wheel zoom
  updates state var via debounced `on_zoom` (Zoom: 13 -> 17); click-on-map
  `on_click=lambda e: my_api.set_view(...)` works; drag-pan works; "Fly to
  center" MapAPI call works; "Locate" with mocked geolocation (51.6,-0.2) fires
  `on_locationfound` -> state shows `{"lat":51.6,"lng":-0.2}`
- `/vector-layers`: circle, circle-marker, polygon, polyline, rectangle all
  render (5 interactive SVG paths + 1 marker); `get_bounds(callback=rx.console_log)`
  logs LatLngBounds to browser console

### dnd demo (react-dnd) — 18/18 PASS on 0.9.9a1 (dev), 18/18 on 0.9.8 (dev)

- index renders demo cards
- `/basic` and `/foreach`: real mouse-down/move/up HTML5 drag of the card into
  another drop target; `collected_params.is_over` turns the hovered target green
  mid-drag (verified via computed style while holding the drag); `on_drop` fires
  toast + moves card via state; drag back works
- `/kanban`: create 2 columns + 2 items via forms; drag item card between columns
  (drop preview card rendered green via `can_drop`/`item_by_id` LambdaVar logic —
  the `@rxe.static` client-side path — works at runtime on 0.9.9a1);
  `on_end` toast fires; column reorder by dragging a column heading onto the other
  column; localStorage persistence survives reload (`on_load` restores board)

## Anomalies / quirks observed (all present on BOTH versions unless noted)

1. **[0.9.9a1-only, minor]** `DeprecationWarning: console.error has been
   deprecated in version 0.9.9 ... (reflex_enterprise/app.py:120)` on the
   not-logged-in exit path (see above).
2. `@rx.memo` without-annotations DeprecationWarnings (9 components) and
   "Passing base-component prop(s) `key` to `@rx.memo`" warnings for the dnd
   demo — identical on 0.9.8 (20 occurrences each); demo-code hygiene, not a
   0.9.9a1 issue. Same for "Passing strings to disable_plugins" and "Implicit
   Radix Themes enablement" warnings (both versions).
3. OSM tile fetches (`*.tile.openstreetmap.org`) fail with
   `net::ERR_TUNNEL_CONNECTION_FAILED` in this sandbox (proxy blocks the host) —
   77 failed requests per map driver run on BOTH versions. Environmental, not
   reflex. Map interactions all work regardless (leaflet panes/SVG don't need
   tile bitmaps).
4. The `is_over` green highlight on `/foreach` appears with a slightly longer
   delay than `/basic` (first driver run sampled the color too early and saw
   blue; with a 2.5 s poll-while-holding it always goes green on both pages and
   both versions). Not judged a bug.
5. **Prod mode untestable (both versions, licensing — SKIPPED, not a bug).**
   `reflex run --env prod` with rxe.App exits at startup: "`reflex run --env
   prod` requires a paid Reflex subscription (one of pro, team, enterprise)."
   (`reflex_enterprise/utils.py` check_prod_mode_in_tier; `CI=1` does not bypass
   it, only dev-mode `_check_login` honors CI). Confirmed identical on 0.9.8
   (`logs/dnd_098_prod_gate.log`) and 0.9.9a1 (`logs/dnd_099a1_prod.log`). The
   gate was not circumvented. Two side observations from the attempts:
   (a) on 0.9.9a1 a first attempt with distinct ports exits earlier with "In
   prod mode, frontend and backend must run on the same port." — single-port is
   now mandatory in prod; (b) the prod-gate exit path also triggers the
   `console.error` DeprecationWarning, here at `reflex_enterprise/utils.py:119`
   (same pattern as anomaly 1).

## Artifact map

- `map/`, `dnd/` — demo app sources (copies of reflex-enterprise/demos, no edits;
  `.web`/`.states`/venvs excluded)
- `drivers/common.py` — Playwright harness (console/network capture, proxy
  bypass for localhost, mocked geolocation)
- `drivers/drive_map.py`, `drivers/drive_dnd.py` — the end-to-end drivers
- `repro_finding001_dnd_can_drop.py` — minimal FINDING-001 trigger (dnd path)
- `logs/` — full server logs for every run + repro outputs
- `shots/map_099a1`, `shots/map_098`, `shots/dnd_099a1`, `shots/dnd_098` —
  screenshots + `capture.json` (all console messages, failed requests) per run
- `pkgjson/` — `.web/package.json` per demo per version.
  Diff 0.9.8 -> 0.9.9a1 (both demos): react-router 7.18.2 -> 8.3.0
  (react-router-dom dropped), vite 8.0.16 -> 8.2.0, postcss override removed.
  Enterprise deps identical across versions (leaflet 1.9.4, react-leaflet 5.0.0,
  react-dnd 16.0.1, react-dnd-html5-backend 16.0.1).

## VERIFICATION (adversarial re-check, 2026-08-28)

Independently verified by a separate agent in fresh PyPI-only venvs
(`$SB/apps/verify_ent_map_dnd_0/{v099,v098}`, Python 3.11,
`reflex==0.9.9a1`/`reflex==0.9.8` + `reflex-enterprise==0.9.4`). **VERDICT:
CONFIRMED** — genuine regression; classified as a **reflex-enterprise
incompatibility caused by an intentional reflex-base 0.9.9a1 breaking change**
(PR #6382 "Move more globals to RegistrationContext").

1. **Repro reproduced bit-for-bit.** `repro_finding001_dnd_can_drop.py`:
   exit 1 on 0.9.9a1 with the exact
   `AttributeError: module 'reflex.components.dynamic' has no attribute
   'bundled_libraries'` at `reflex_enterprise/vars.py:143`; exit 0 on 0.9.8
   (same enterprise 0.9.4 wheel in both envs).
2. **Mechanism verified in the published wheels.** reflex-base 0.9.8
   `components/dynamic.py:35` defines module-level
   `bundled_libraries = list(DEFAULT_BUNDLED_LIBRARIES)` (wildcard re-exported
   via `reflex.components.dynamic`); reflex-base 0.9.9a1 moves the list onto
   `RegistrationContext.ensure_context().bundled_libraries` and provides **no
   module `__getattr__`/alias shim** (checked wheel + release checkout source).
   `bundle_library()` itself still exists and works on 0.9.9a1.
   reflex-enterprise 0.9.4 `vars.py:143`
   (`_validate_and_extend_return_expr`) reads `dynamic.bundled_libraries`.
3. **All four trigger-scoping claims verified** (`scope_checks.py`, run on both
   versions): plain lambda without VarData -> OK/OK; `@rxe.static` lambda with
   bundled-library imports -> OK/OK (validator skipped); state-var lambda ->
   identical "cannot use hooks" ValueError on BOTH versions (pre-existing, not
   a regression); plain lambda with bundled-library imports -> OK on 0.9.8,
   AttributeError on 0.9.9a1. So the shipped demos escape exactly as claimed
   and the crash needs non-static + import-carrying VarData without hooks.
4. **Refutations attempted, all failed:**
   - *Misuse / version mismatch?* No — reflex-enterprise 0.9.4 declares
     `reflex[db]>=0.9.6` with **no upper bound**, so 0.9.9a1 + 0.9.4 is a legal
     (and default) resolution, and 0.9.4 is the **newest** reflex-enterprise on
     PyPI (releases end at 0.9.4/0.9.4a4 — no fixed prerelease exists to pair
     with 0.9.9a1).
   - *App bug?* No — the repro uses the officially supported
     `bundle_library()` mechanism; enterprise's own error message at
     vars.py:146-150 instructs users to call it, i.e. this validator exists to
     serve exactly this pattern.
   - *Pre-existing?* No — 0.9.8 passes; only the state-var variant is
     pre-existing and it fails identically on both versions.
   - *Env quirk?* No — clean uv venvs, PyPI-only, provenance of both packages
     confirmed via `__file__`.
5. Corroboration: fix branch `origin/claude/reflex-enterprise-shim-mvevpt`
   (commit 5bda46ce8, not in the release branch) independently restores
   `dynamic.bundled_libraries` as a deprecated shim and notes every published
   reflex-enterprise 0.8.0-0.9.4a4 reads this attribute.

Verifier repro dir: `$SB/apps/verify_ent_map_dnd_0/` (`v099/`, `v098/`,
`repro_finding001_dnd_can_drop.py` copy, `scope_checks.py`). No servers were
started during verification.

## VERIFICATION — console.error DeprecationWarning on enterprise gate paths (adversarial re-check, 2026-08-28)

Separate verifier for anomalies 1 and 5(b) (console.error DeprecationWarning at
`reflex_enterprise/app.py:120` login gate and `reflex_enterprise/utils.py:119`
prod gate on 0.9.9a1). **VERDICT: CONFIRMED** — genuine, reproduced from a
minimal fresh app in clean PyPI-only venvs. Classified as a
**reflex-enterprise incompatibility** (latest published enterprise calls a
reflex-base API deprecated in 0.9.9), **cosmetic/low severity, not a
functional regression** (gates behave identically on both versions; only the
warning line is new, and it is the intentional 0.9.9 console-API deprecation
firing as designed).

Independent repro (minimal `rxe.App`, NOT the demos — `gate_app/` under
`verify_console_deprecation/`), run matrix with venvs
`$SB/apps/verify_ent_map_dnd_0/{v099,v098}` (provenance re-confirmed:
reflex 0.9.9a1/0.9.8 + reflex-enterprise 0.9.4 from PyPI, no CI/REFLEX_ACCESS_TOKEN
env vars, no `~/.reflex` token on the box):

| run | cmd | result |
|-----|-----|--------|
| 0.9.9a1 dev, no CI | `reflex run --frontend-port 3844 --backend-port 8844` | `DeprecationWarning: console.error has been deprecated in version 0.9.9 ... (reflex_enterprise/app.py:120)` then login-gate msg, exit |
| 0.9.9a1 prod, CI=1 | `reflex run --env prod --frontend-port 3845 --backend-port 3845` | same warning at `reflex_enterprise/utils.py:119` then prod-gate msg, exit |
| 0.9.8 dev, no CI | same | login-gate msg, **no** DeprecationWarning |
| 0.9.8 prod, CI=1, single port | same | prod-gate msg, **no** DeprecationWarning |

Logs: `verify_console_deprecation/logs/gate_{099a1,098}_{dev_nologin,prod_ci}.log`.
Neither licensing gate was circumvented — every run exited at the gate.

Mechanism verified in the published wheels:

- reflex-base 0.9.9a1 `reflex_base/utils/console.py` deprecates the whole
  `console.*` logging API (`_shim_deprecation`, `deprecation_version="0.9.9"`,
  removal 1.0) — present in the release checkout source too, i.e. intentional;
  0.9.8's `console.error` has no shim.
- reflex-enterprise 0.9.4 wheel calls `console.error` at exactly `app.py:120`
  (`_check_login`) and `utils.py:119` (`check_prod_mode_in_tier`), both invoked
  from `AppEnterprise.__post_init__`; the wheel has 18 `console.*` call sites
  across 9 files, but none fired on the successful CI=1 demo runs (0 console.*
  deprecations in `map_099a1_run2.log`/`dnd_099a1_run1.log`), so the two
  error-path sites are the user-visible ones.
- PyPI re-checked 2026-08-28: newest reflex-enterprise is 0.9.4 (prereleases end
  at 0.9.4a4), and 0.9.4 declares `reflex[db]>=0.9.6` with no upper bound — so
  every enterprise user resolving 0.9.9a1 gets this noise and cannot fix it
  themselves.

Refutations attempted: env quirk (no — clean venvs, warning is plain Python,
attribution frame points into the enterprise wheel), app bug (no — reproduces
with a 3-line minimal app; demo code never calls console.error), pre-existing
(no — 0.9.8 baseline clean on both paths), misuse (no — running logged-out /
attempting prod are exactly the states these gates exist for). Side note: the
"prod requires same frontend/backend port" error also occurs on 0.9.8
(`gate_098_prod_ci.log` first attempt with distinct ports), so that part of
anomaly 5(a) is not 0.9.9a1-specific.

Actionable fix lives in reflex-enterprise (migrate console.* -> logging, or a
coordinated 0.9.9-compatible release); nothing to change in reflex-base unless
the team wants deprecation shims to stay silent for first-party callers.
No servers were left running by this verification.

## VERIFICATION — prod-mode subscription gate (anomaly 5; adversarial re-check #2, 2026-08-28)

Independently re-verified by a separate agent in fresh PyPI-only venvs
(`$SB/apps/verify_ent_map_dnd_2/{v099,v098}`, Python 3.11, `reflex==0.9.9a1` /
`reflex==0.9.8` + `reflex-enterprise==0.9.4`, provenance confirmed via
`importlib.metadata` + `__file__`), running the unmodified `dnd` demo copied
from this artifacts dir. **VERDICT: facts CONFIRMED, but NOT a defect — no
regression, nothing for a fix-agent to act on.** It is intentional
reflex-enterprise licensing behavior, identical on 0.9.8, and the coverage gap
is narrower than claimed (see point 4). Logs: `logs/verifier2_*.log`.

1. **Gate reproduced on both versions** (`CI=1 ... reflex run --env prod
   --frontend-port <P> --backend-port <P>`): both exit before compiling with
   "`reflex run --env prod` requires a paid Reflex subscription (one of pro,
   team, enterprise)." — 0.9.9a1 port 8848 (`verifier2_A_...`), 0.9.8 port 8849
   (`verifier2_C_...`). Same `console.error` DeprecationWarning at
   `reflex_enterprise/utils.py:119` on 0.9.9a1 only. NOT a regression.
2. **Mechanism verified in the wheel, with one naming correction:** the gate is
   `check_paid_tier_for_command` (`reflex_enterprise/utils.py:82`), not
   "check_prod_mode_in_tier" as the original evidence said. It is called from
   `AppEnterprise.__post_init__` (`app.py:45`) whenever compile context is
   EXPORT, or RUN + prod mode; `get_user_tier()` returns "anonymous" without a
   token; the only skip is `is_in_app_harness()`. The `CI` /
   `REFLEX_BACKEND_ONLY` bypass exists only in `_check_login` (`app.py:113-114`)
   — confirmed: CI does not bypass the paid-tier gate (and `reflex export` is
   gated by the same function, so exporting is no workaround either).
3. **Side observation "0.9.9a1 newly requires frontend-port == backend-port in
   prod" is REFUTED — it is pre-existing.** The identical check (env in
   PROD/PREVIEW and both ports given and different -> error + SystemExit(1))
   exists in the 0.9.8 wheel (`reflex/reflex.py:335`) and the 0.9.9a1 wheel
   (`reflex/reflex.py:358`), byte-identical logic. Empirically: 0.9.8 with
   `--frontend-port 3849 --backend-port 8849 --env prod` exits with the same
   "In prod mode, frontend and backend must run on the same port."
   (`verifier2_D_098_prod_diffports.log`), exactly like 0.9.9a1
   (`verifier2_B_...`). The original tester only tried distinct ports on
   0.9.9a1 and inferred novelty.
4. **"Cannot be tested in prod mode without a paid subscription" is
   overstated.** reflex-enterprise deliberately exempts reflex's app harness:
   `APP_HARNESS_FLAG=1` in the environment (what `reflex.testing.AppHarness` /
   `AppHarnessProd` set) makes `is_in_app_harness()` true and the gate returns
   early. Verified: `CI=1 APP_HARNESS_FLAG=1 ... reflex run --env prod
   --frontend-port 8850 --backend-port 8850` proceeds past the gate — page
   compile completes (Compiling 100% 18/17) and frontend package install starts
   (`verifier2_E3_099_prod_harnessflag.log`). So prod
   hydration/memoization of enterprise components IS testable without a
   subscription via the sanctioned harness path (`AppHarnessProd`), which is
   precisely what reflex's own prod integration tests use. Side effect of the
   flag: `TEST_MODE` is set for the frontend build (`reflex/utils/build.py:25`).
5. **Why no full prod run is archived here:** all 3 attempts (with/without
   capped `BUN_CONFIG_MAX_HTTP_REQUESTS`) died ~7 min in during `bun add` of
   dev dependencies with repeated `error: ConnectionClosed downloading package
   manifest ...` against registry.npmjs.org, while `curl` to the same manifest
   URLs returned 200 in <0.2s — sandbox-proxy flakiness for bun's connection
   pattern at test time (reflex writes `fetch-retries=0` into `.web/.npmrc`,
   hardcoded in `reflex_base/constants/installer.py:87`, so one dropped
   connection is fatal). Environmental, unrelated to the gate; earlier dev-mode
   installs of the same demo succeeded in this sandbox.

Conclusion: anomaly 5 stands as documented context (SKIPPED coverage, licensing
by design, identical on both versions) with two corrections (function name;
same-port requirement is not new) and one workaround (AppHarnessProd /
`APP_HARNESS_FLAG` is the supported unlicensed prod-testing path — a follow-up
agent wanting prod coverage of enterprise components should drive the demos via
`AppHarnessProd` rather than raw `reflex run --env prod`, and needs working npm
registry access). No reflex 0.9.9a1 defect, no reflex-enterprise
incompatibility. Verifier working dir: `$SB/apps/verify_ent_map_dnd_2/`
(`v099/`, `v098/`, `dnd/`, `logs/`). All spawned processes killed (verified via
`ps`; ports 8848-8850 free).
