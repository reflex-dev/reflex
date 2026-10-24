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
  (and the sdist archive itself) contain: reflex-components-core 33/36 (`base/error_boundary.pyi`, `core/banner.pyi`,
  `core/upload.pyi` missing), reflex-components-dataeditor 0/1 (`dataeditor.pyi`), reflex-components-radix 64/65
  (`primitives/form.pyi`). Control: the 0.10.0 sdists build with all 36 / 1 / 65 stubs. Root cause (reproduced): the
  `[tool.hatch.build.hooks.reflex-pyi].dependencies` list names `reflex-base` (and core/lucide/sonner) **unpinned**, so the
  isolated build env resolves **reflex-base 0.10.0** (stable) while building a1 sources; hatch-reflex-pyi regenerates the
  stubs against it and silently drops the modules that need base 0.10.1a1 (rc 0, no warning). Building the same sdist in a
  non-isolated env with reflex-base 0.10.1a1 yields all 36 stubs; with reflex-base 0.10.0 only 32.
