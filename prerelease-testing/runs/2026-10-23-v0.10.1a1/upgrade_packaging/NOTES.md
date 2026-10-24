# upgrade_packaging — reflex 0.10.1a1 vs 0.10.0 (2026-10-24)

Item: in-place upgrades of reflex-examples apps, `.web/package.json` diffs, Bun 1.4.4, install matrix (Python
3.11-3.15, pip + uv), `#7440` reflex.model without greenlet, mixed sibling floors, sdists (`#7411`), `reflex init`
(`#7556`), third-party sweep, docs `#7646`.

Environment: `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`, work dir
`W=$SB/apps/upgrade_packaging/upgrade` (staged with `fixtures/upgrade/bin/stage.sh`, `VENV_PREFIX=upgrade_packaging`,
`NEW=new`, `PREV=prev`). Ports 3460-3499 / 8460-8499. Every command below runs with cwd=`$SB` (never a checkout) and
`uv --no-config`.

Rerun recipe (from a fresh shell):
```bash
export SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
export W=$SB/apps/upgrade_packaging/upgrade NEW=new PREV=prev VENV_PREFIX=upgrade_packaging
cd $SB && bash /home/user/wt-testing/prerelease-testing/fixtures/upgrade/bin/stage.sh
```

## Harness notes (not product findings)

- The shared `$SB/envs/prev` venv is NOT a pure 0.10.0 graph: it was built with `--prerelease=allow`, so it holds
  reflex-components-code 0.10.1a1, reflex-components-moment 0.10.1a1, reflex-components-lucide 1.1.1a1 and
  reflex-hosting-cli 0.2.1a1 next to reflex/reflex-base/core/radix/dataeditor 0.10.0. Every 0.10.0 baseline in this
  item uses its own venv resolved WITHOUT a prerelease flag (`uv pip install 'reflex[db]==0.10.0'` or pip without
  `--pre`), which yields the final 0.10.0 train (code/moment 0.10.0, lucide 1.1.0, hosting-cli 0.2.0).
- `/apps/upgrade_sweep` (filesystem root) pre-existed from an earlier campaign; a first staging attempt of this item
  briefly created `/apps/upgrade_packaging` (an `export A=.. B=$A` ordering slip) and was removed again.

## Sections

(filled in incrementally below)

## 1. Install matrix (PKG-09 / PKG-08 / PKG-05, F-006) — PASS

`SPECS="uv311:uv:3.11:db uv312 … uv315 pip311 … pip315 f006pip312:pip:3.12:plain f006uv312:uv:3.12:plain" bash $W/inst/bin/n001.sh`
(log `inst/logs/n001-matrix.out`, freezes `inst/logs/freeze-*.txt`). Python 3.15 = cpython 3.15.0b4 (uv-managed).

- `reflex[db]==0.10.1a1` installs with rc 0 on **3.11, 3.12, 3.13, 3.14, 3.15** with both uv (`--prerelease=allow`) and
  uv-seeded pip (no `--pre`): sqlalchemy 2.1.6 + **greenlet 3.5.6** + sqlmodel 0.0.48 + alembic 1.20.1, pydantic 2.14.1,
  `import reflex.model` OK, `pip check` / `uv pip check` clean everywhere.
- **Resolution differs by installer** (expected PEP 440 semantics, worth knowing for support):
  - pip (no `--pre`): reflex/reflex-base/core/radix/moment **0.10.1a1** but **code 0.10.0, dataeditor 0.10.0, lucide 1.1.0,
    hosting-cli 0.2.0, build-sdk 0.1.0** (the reflex wheel floors them at `>=0.10.0` / `>=1.1.0` / `>=0.2.0`; core is pulled
    to a1 only because radix a1 requires `core>=0.10.1a1`). This is the "mixed sibling floors" graph of §6.
  - uv `--prerelease=allow`: the whole train at a1 (+ `wrapt==2.5.2rc1`, a transitive pre-release uv's flag lets in).
  - Stock `python3.11 -m venv` / `python3.13 -m venv` + pip 24/25 with and without `--pre`: see `stockpip/stockpip.out`.
- `reflex db init / makemigrations / migrate / makemigrations(noop)` on a fresh sqlite db: rc 0, 0 error lines, 1 version
  file, tables `alembic_version` + `note` on uv311, uv315, pip311, pip315 (`inst/logs/dbcli.out`). Plain `reflex==0.10.1a1`
  (no db extra): `reflex db init` rc 1 with "Database is not available. Please install the required packages:
  `pip install reflex[db]`" (PKG-13 still fixed).
- In-place paths (`BASE_VERSION=0.10.0 bash $W/inst/bin/install_paths.sh`, `inst/logs/install_paths.out`): pip
  `pip install -U reflex==0.10.1a1` moves reflex/base/core/moment/radix to a1 even without `--pre` (the explicit alpha pin
  and the `>=0.10.1a1` transitive floors allow it), pip check clean; uv refuses the alpha pin without `--prerelease=allow`
  (hint printed); `reflex[db]==0.10.0 -> reflex==0.10.1a1` keeps the previously installed greenlet.

## 2. #7440 reflex.model without greenlet — PASS (fixed; 0.10.0 positive control fails)

`probes/nogreenlet_probe.py` in venvs built with stock pip: `reflex==0.10.1a1 sqlmodel alembic` (no db extra, greenlet
absent) and the same at 0.10.0 (`logs/nogreenlet-*.json`).
- 0.10.1a1: `import reflex.model` OK (Model/session/asession/get_engine/get_async_engine present), `rx.Model` subclass OK,
  `rx.Model.create_all()` + `rx.session()` insert/select OK; `rx.asession()` raises SQLAlchemy's
  `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed … 'pip install
  sqlalchemy[asyncio]'` (helpful, though it points at `sqlalchemy[asyncio]` rather than `reflex[db]`).
- 0.10.0: `import reflex.model` itself raises that ImportError (positive control).

## 3. Bun 1.4.4 (#7639) and `reflex init` (#7556) — PASS

`bin/init_bun_tests.sh` (`logs/init_bun_tests.out`, logs in `$SB/apps/upgrade_packaging/initbun/logs`). System bun on PATH is
1.4.2 (`/root/.bun/bin/bun`); the default managed dir is `~/.local/share/reflex/bun` (= `REFLEX_DIR/bun`).
- B1 fresh `REFLEX_DIR` + 0.10.1a1 `reflex init`: downloads **bun 1.4.4** into `REFLEX_DIR/bun/bin/bun` (silently, no log line).
- B2 0.10.0 on a fresh `REFLEX_DIR` installs nothing (it accepts the system bun 1.4.2 ≥ its MIN 1.4.0); 0.10.1a1 on the same
  dir then installs the managed 1.4.4 (system 1.4.2 < new MIN 1.4.4).
- B4 a managed bun 1.4.2 pre-seeded in `REFLEX_DIR/bun/bin/bun` is replaced by 1.4.4 on the next 0.10.1a1 `reflex init`.
- B3 `REFLEX_USE_SYSTEM_BUN=1` with bun 1.4.2: 0.10.1a1 logs `Info: Using custom Bun path: /root/.bun/bin/bun` and the new
  text `Warning: Bun 1.4.2 is below the minimum supported version 1.4.4. Please upgrade Bun by running bun upgrade.`, then
  continues with 1.4.2 (rc 0, no managed install). 0.10.0: no warning.
- I1 fresh `reflex init` in a directory named `reflex`: "The app directory cannot be named reflex." on both versions (expected).
- I2 `reflex init --name myapp` in a directory named `reflex` works on both; re-running `reflex init` there: **0.10.1a1 rc 0
  ("Initializing myapp"), 0.10.0 rc 1 "The app directory cannot be named reflex."** → #7556 fixed, control reproduces.
- I3 re-init of an existing app in a normal dir: only `__pycache__/rxconfig.*.pyc` appears (both versions).
- I4 `reflex --version` 0.10.1a1 / 0.10.0; `reflex init --template __bogus__` → "Template `__bogus__` not found or invalid."
  (rc 1, no list of templates on either version); `reflex export` of the blank app: rc 0, backend.zip + frontend.zip, 0
  errors on both. Templates in dev + prod: see §8 (smoke).

## 4. #7411 sdists — PARTIAL FAIL (two findings)

`bin/sdist_matrix.sh` (`logs/sdist_matrix.out`, per-package logs + RECORD file lists in `$SB/apps/upgrade_packaging/sdist/`),
`bin/sdist_pyi_control.sh` (`logs/sdist_pyi_control.out`).
- Every changed package installs from its sdist with **pip** (`pip install --no-binary <pkg> <pkg>==<ver>`): reflex,
  reflex-base, components-code/core/dataeditor/moment/radix, lucide 1.1.1a1, hosting-cli, reflex-release, build-sdk: rc 0.
- **uv** (`uv pip install --prerelease=allow --no-binary <pkg> …`): all rc 0 EXCEPT **`reflex` 0.10.1a1**: the build backend
  hook (`scripts/hatch_build.py`, `require-runtime-dependencies = true`) makes the isolated build env need the runtime
  deps, which include `reflex-components-radix>=0.10.1a1` → `reflex-components-core>=0.10.1a1`; uv does not allow
  pre-releases in build environments ("build environments can't opt into pre-releases automatically"), so
  `uv pip install --no-binary reflex reflex==0.10.1a1` fails to resolve `build-system.requires`
  (`sdist/logs/sdist-uv-reflex.log`). Alpha-train specific; a final release with final floors would not hit it.
- **Stub regression**: the wheel that pip/uv build from the 0.10.1a1 sdist is missing `.pyi` stubs that the published wheel
  (and the sdist archive itself) contain: reflex-components-core 32/36 (`base/error_boundary.pyi`, `core/banner.pyi`,
  `core/upload.pyi`, `el/elements/forms.pyi` missing), reflex-components-dataeditor 0/1 (`dataeditor.pyi`), reflex-components-radix 64/65
  (`primitives/form.pyi`). Control: the 0.10.0 sdists build with all 36 / 1 / 65 stubs. Root cause (reproduced): the
  `[tool.hatch.build.hooks.reflex-pyi].dependencies` list names `reflex-base` (and core/lucide/sonner) **unpinned**, so the
  isolated build env resolves **reflex-base 0.10.0** (stable) while building a1 sources; hatch-reflex-pyi regenerates the
  stubs against it and silently drops the modules that need base 0.10.1a1 (rc 0, no warning). Building the same sdist in a
  non-isolated env with reflex-base 0.10.1a1 yields all 36 stubs; with reflex-base 0.10.0 only 32.

## 5. In-place upgrades of reflex-examples apps 0.10.0 -> 0.10.1a1 (`up/`)

Base venvs: `bash $W/up/bin/build_base_venvs.sh fd:form-designer twr:twitter-redis gh:github-stats upload:upload nba:nba`
(= `-r requirements.txt 'reflex==0.10.0'`, no prerelease flag → pure 0.10.0 train). Upgrade step = the fixture's
`uv pip install --prerelease=allow -U 'reflex[db]==0.10.1a1' 'pydantic<2.15'` in the same venv / app dir / `.web` /
`reflex.lock` / db / Chromium profile. Outputs: `up/seq_*.out`, `up/pkg/` (package.json snapshots + diffs), `up/freeze/`.

| app | base 0.10.0 | in place 0.10.1a1 | prod | cold (`rm -rf .web`) | notes |
|---|---|---|---|---|---|
| form-designer (reflex[db] + reflex-local-auth 0.5.0), `seq_fd.sh` 3490/8490 | full 18/0/2, entry 14/0/1 | 12/0/1, entry 14/0/1; first load keeps `_auth_token`, 0 changing storage writes | 12/0/1, 15/0/0; `/edit/form/1` `/form/1` `/responses/1` 200, `/nope` 404, `/login` 307 | 12/0/1 | == fixture expectation; `makemigrations` after upgrade: no new revision (2 files) |
| twitter prod + Redis, `seq_twr.sh` P=3498 RP=8499 | 19/0/2 (9 granian workers) | stale tab 8/0/3, old pickled sessions 12/0/2 (no re-login), new users 19/0/2; **8 workers** (#7542 cap) | — | — | rollback to the 0.10.0 freeze on the same Redis: 10/2/2 — both "FAIL"s are the driver expecting sessions to reset (they survive a 0.10.1a1 → 0.10.0 rollback: same pickle schema), no crash; F-019 `Frontend version 0.10.0 … does not match` log line only |
| github-stats (httpx, GraphQL stub), `seq_gh.sh` 3492/8492/8498 | 14/0/2 | 12/0/2 (LocalStorage users/stats restored) | 13/0/1 | 14/0/2 | == fixture expectation; anomalies pre-existing (React value-without-onChange, widget theme) |
| upload (react-dropzone, hostile names, 12 MB sha256 roundtrip, throttled upload + cancel), `seq_app.sh upload` 3486/8486 | 21/0/0 | 21/0/0 | — | 21/0/0 | `up/seq_upload2.out`; first run hit a fixture bug (`drive_upload.py` uses `run.expected_bad`, missing from `harness.py`): `harness.py` patched (test code, copy in `up/harness.py.patched`), re-run |
| nba (pandas/plotly) | SKIPPED | | | | the fixture's nba patch reads `nba_local.csv` which `stage.sh` does not provide and media.geeksforgeeks.org is unreachable from the sandbox |

`.web/package.json` diff base → in place (every app, `up/pkg/*-up.from-*-base.package.diff`): only `react` / `react-dom`
19.3.0 → **19.3.1**, `vite` 8.3.2 → **8.3.4**, `postcss` 8.5.29 → **8.5.30**, `postcss-import` 17.0.0 → **17.0.1**, and
where used `@radix-ui/react-accordion` 1.2.20 → 1.3.1, `@radix-ui/react-form` 0.1.16 → 0.3.0, `react-syntax-highlighter`
16.1.1 → 16.1.2 (form-designer). Nothing else moves. In place vs cold: byte-different only because bun pretty-prints the
file it rewrites in place while a cold init leaves reflex's single-line render; **normalized JSON is identical**
(`fd-up` vs `fd-cold`: equal). `reflex.lock/package.json == .web/package.json` after every run. `.web` file list in place
vs cold: identical; in place vs base: the Errorboundary component hash changes and `.web/vite-plugin-react-compiler.js`
appears (#7234). With bun (default) 0.10.0 already wrote `devDependencies` (bun reads `-d` as `--dev`), so no migration
is needed there; the npm case (#7566) is in §7.
Server logs: no new warnings on 0.10.1a1 beyond the fixture's known-benign set (pydantic serializer warning in
form-designer, `script "dev" exited with code 143`, granian worker-count warning with Redis, F-019 stale-tab line).

## 6. Blank-app smoke per Python (`smoke/bin/seq_smoke.sh new upgrade_packaging-n001-pip311 upgrade_packaging-n001-uv315`, 3488/8488)

`reflex init --template blank` rc 0 (no npmmirror fallback), dev 6/1 (the FAIL is the known SPA fallback: dev answers unknown
routes with 200 on every version), prod 6/0/1 (`/ping` 200, `/sitemap.xml` 200, `/nope` 404, favicon 404 benign) on
3.12 (new), 3.11 (pip) and 3.15 (uv). Generated `.web/package.json` identical across the three (md5 8df058ca).

## 7. Third-party sweep (`tp/`)

`TP_EXTRA='pydantic<2.15' bash $W/tp/bin/build_venv.sh` (0.10.1a1 + the 22 pinned packages + authlib +
google-api-python-client): resolves, `uv pip check` clean. `tp/probes/import_sweep.py` vs `tp/expected/import_sweep.json`:
**22/22 SAME** (reflex-chakra `_issubclass` ImportError and community reflex-ag-grid `reflex.base` fail as on every version
since 0.9.12; reflex-clerk 1 authlib warning). New on 0.10.1a1 while importing: reflex-chat's `rx.el.input(id='Chat_n1')`
now logs the #7386 deprecation "Submitting the form control with id 'Chat_n1' by its `id` has been deprecated in version
0.10.1 … It will be completely removed in 0.11.0" (downstream package will need `name=`). Auth demos: see §9.

## 8. Docs #7646

`docs/hosting/self-hosting.md` at `v0.10.1a1` documents `REFLEX_BACKEND_START_METHOD` (fork/spawn/forkserver) and
`REFLEX_STRICT_HOT_RELOAD` for the Granian backend; both env vars exist in `reflex_base/environment.py` at the tag
(`REFLEX_BACKEND_START_METHOD: EnvVar[Literal["fork","spawn","forkserver"] | None]`). CHANGELOG top entry lists the
packaging items (#7411, #7440, #7566, #7554/#7556, #7639) and matches the observed behaviour.

## 9. Third-party auth demos on 0.10.1a1 (`tp/bin/seq_tp.sh upgrade_packaging-tp new`, `tp/bin/run_google.sh`) — PASS

- reflex-local-auth 0.5.0 demo dev (3463/8463), prod (8467), prod + Redis (8469): **36/38 each**, 0 differing checks and 0
  console-anomaly differences vs `tp/expected/local_auth-*.json`, 0 tracebacks / TypeErrors in the server logs (the 2
  known failures are the `_validate_fields` subclass-override pair).
- reflex-magic-link-auth 0.2.2 demo dev + prod (`ML_FORCE_DEV=1`): **10/11 each**, 0 differing (known `/check-your-email`
  bounce), per-IP OTP rate limit trips at attempt 6 as expected.
- reflex-google-auth 0.2.0 demo dev: **12/13** (the driver's "key discoverable" check), 0 differing; the 11 console
  anomalies are the sandbox's blocked Google endpoints (`net::ERR_TUNNEL_CONNECTION_FAILED`), as on every pass.

## 10. Mixed sibling floors (`mixed/`)

App `mixed/mixedapp` (forms with checkbox/switch/id-only input/repeated names, `rx.window_event_listener`,
`rx.clipboard`, `rx.data_editor` with state-backed columns (first column without `type`/`id` unless
`MIXED_TYPED_COLUMNS=1`), `rx.icon` static + dynamic, `rx.code_block` + `rx._x.code_block(use_transformers=True)`,
`rx.moment`), driver `mixed/drive_mixed.py`, runner `mixed/run_mixed.sh <venv> <label> dev|prod` (3470/8470). Graphs:
- `new` = everything 0.10.1a1 (uv `--prerelease=allow`);
- `upgrade_packaging-n001-pip312` = what a stock `pip install reflex[db]==0.10.1a1` (no `--pre`) gives: reflex, base,
  core, radix, moment 0.10.1a1 + **reflex-components-code 0.10.0, dataeditor 0.10.0, lucide 1.1.0, hosting-cli 0.2.0**;
- `prev` (the campaign's shared venv) = the reverse: reflex/base/core/radix/dataeditor 0.10.0 + code 0.10.1a1, moment
  0.10.1a1, lucide 1.1.1a1 (core/radix/dataeditor a1 require `reflex-base>=0.10.1a1`, so they cannot be installed next
  to reflex 0.10.0; code/moment/lucide a1 only require `reflex-base>=0.10.0` and can);
- `upgrade_packaging-pure-prev` = pure 0.10.0 baseline.

Results (dev; `mixed/logs/run-mixed-<label>.out`, JSON + screenshots in `$SB/apps/upgrade_packaging/mixed/out`):
- **new (all a1), untyped state column**: 22/23 checks pass (the one FAIL was a too-strict driver assertion on the
  dynamic icon's class, fixed in the driver afterwards): lucide static + dynamic icons render, shiki block with the
  `[!code highlight]` transformer applied (#7437), react-syntax-highlighter block, moment, data_editor with an untyped
  state column renders (#7607) and `on_cell_clicked` fires, form submit → `{"agree": true, "choice": "a", "idonly":
  "idval", "sw": true, "tag1": "t1", "tag2": "t2", "tags": "t2", "username": "ada"}`, window keydown and clipboard paste
  handlers fire, reload re-hydrates. Compile-time deprecations: `Submitting the form control with id 'idonly' by its
  id has been deprecated in version 0.10.1 …` (#7386, expected) and the pre-existing "Implicit Radix Themes enablement"
  one. **But** 4× `[Reflex Frontend Exception] TypeError: Cannot read properties of undefined (reading '0')` from
  `@glideapps/glide-data-grid … eventListener` during the data_editor interaction (see the isolation runs below).
- **pip312 (mixed, dataeditor 0.10.0 + base a1)**: compile logs `DeprecationWarning: format_data_editor_column has been
  deprecated in version 0.10.1. Upgrade reflex-components-dataeditor; rx.data_editor now fills in its column defaults
  itself` (the intended hint), then the page **crashes** in `<ForwardRef(DataGrid)>` (`TypeError: Cannot read properties
  of undefined (reading 'includes') at truncateString`) = bug #7596, which dataeditor 0.10.1a1 fixes but a `--pre`-less
  pip user never receives (reflex floors dataeditor at `>=0.10.0`). Same crash on `prev` and `pure-prev` (0.10.0).
- Typed-column variants (every graph can render) and prod runs: see the table appended below once finished.

Incidental re-verification of the registry's open-unfiled "no dispatch function when the app package has no
`__init__.py`" (#7304): the probe apps were first run WITHOUT `__init__.py`. 0.10.0 (`pure-prev`): every state update
fails with `Cannot process state update: no dispatch function for substate(s) "reflex___state____state.deapp____state"`
(buttons do nothing, `nrows` stays 3); 0.10.1a1: state updates apply, 0 console errors → **fixed**, control reproduces.
`__init__.py` was then added for the remaining baseline runs (`*-typed2` / `pureprev2` labels).

data_editor isolation (`mixed/deapp`, driver `drive_deapp.py`, 3474/8474; all columns typed; hover sweep + click after
each mutation): `new` 0 page errors across in-place append, reassign, column append, reset, reload; `pip312`
(dataeditor 0.10.0) 0 page errors; `pure-prev` 0 page errors (but state updates inert, see #7304 above).

Typed-column dev runs (`MIXED_TYPED_COLUMNS=1`, every graph renders):
| graph | checks | page errors | notes |
|---|---|---|---|
| new (all a1) | **23/23** | 4× glide `reading '0'` at page load | shiki `[!code highlight]` applied (#7437 fixed), icons/moment/forms/keydown/paste OK |
| pure-prev (0.10.0) | 22/23 | the same 4 glide errors at page load | the FAIL is the shiki transformer (`highlighted: 0`, #7430 reproduces on 0.10.0 = positive control); form data identical to a1 (`agree: True, sw: True, idonly: 'idval'`) |
The 4 `TypeError: Cannot read properties of undefined (reading '0')` from `@glideapps/glide-data-grid … eventListener`
occur at page load on BOTH versions (timestamps = hydration, before any interaction) and not in the `deapp` isolation
app, so they are context, not a regression (probably the second, literal editor `columns=[{"title": "Lit"}, …]`,
`data=[["x", 1]]`, `height="120px"`). The React warning `Checkbox is changing from uncontrolled to controlled` after the
form submit is also on both versions.
