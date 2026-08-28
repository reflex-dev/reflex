# Cluster: pydantic_optional — reflex 0.9.9a1 (PR #6786: pydantic now optional)

Tested 2026-08-28 against PyPI packages only (never the local checkout).
Intended mechanism (from PR #6786 + release source): pydantic removed from
`reflex-base` hard deps; support activates via module-level `find_spec("pydantic")`
guards in `reflex_base/vars/object.py`, `reflex_base/utils/serializers.py`,
`reflex_base/event/processor/base_state_processor.py`, `reflex/istate/proxy.py`,
`reflex/model.py`. Extras: `reflex[pydantic]` -> `reflex-base[pydantic]`;
`reflex[db]` pins pydantic + sqlmodel + alembic.

## Venvs used (all installed from PyPI with `uv pip install --prerelease=allow`)

| venv | contents |
|---|---|
| `envs/pyd_bare` | `reflex==0.9.9a1` (no pydantic) |
| `envs/pyd_extra` | `reflex[pydantic]==0.9.9a1` + explicit `pydantic==2.13.4`* |
| `envs/pyd_db` | `reflex[db]==0.9.9a1` + explicit `pydantic==2.13.4`* |
| `envs/pyd_098` | `reflex==0.9.8` (baseline), later upgraded in place to 0.9.9a1 (test d) |

*CAUTION: `--prerelease=allow` applies to ALL packages in uv, so the extras
initially resolved pydantic to the **2.14.0b1 beta**. Re-pinned to stable 2.13.4
to match what a real `pip install reflex[pydantic]` user gets.

## Apps and drivers (in this directory)

- `dc_app/` — dataclass + plain-dict state vars (bare install). Driver: `drive_dc.py`.
- `pyd_app/` — pydantic v2 models: nested model, list-in-model, list[Model] +
  `rx.foreach`, computed var `model_dump_json`, event handler with model-hinted
  arg fed a dict from the frontend. Driver: `drive_pyd.py`.
- `pyd_app_098/` — identical app source, initialized under 0.9.8 (baseline +
  in-place-upgrade target). Same driver.
- `db_app/` — `reflex[db]`: `rx.Model` table, `rx.session` CRUD via UI, sqlite.
  Driver: `drive_db.py`. (`rxconfig.py` sets `db_url`; tables created via
  `reflex.model.create_all()` at app import — alembic init intentionally skipped,
  which produces a benign "Database is not initialized, run reflex db init first"
  warning in the log.)

Rerun pattern (from this dir; each app in its own venv, ports 3300-3319/8300-8319):

```
$SB/envs/<venv>/bin/reflex run --frontend-port 330X --backend-port 830X --loglevel debug
$SB/envs/driver/bin/python drive_<app>.py http://localhost:330X/ <shot-prefix>
```

Do NOT override NO_PROXY when launching reflex in this sandbox — the inherited
NO_PROXY already contains registry.npmjs.org; overriding it with just
"localhost,127.0.0.1" forces bun through the TLS-intercepting proxy and every
`bun add` dies with `error: ConnectionClosed downloading package manifest ...`
(that cost three failed launches; environment quirk, not a framework bug).
First launch of a fresh app is much faster if you hardlink-prefill `.web/`
(node_modules, bun.lock, package.json, reflex.install_frontend_packages.cached)
plus root `reflex.lock` from an already-built app of the same reflex version.

## Results

### (a) bare `reflex==0.9.9a1` — PASS
- pydantic absent from `uv pip list`; `find_spec("pydantic") is None`.
- `python -X importtime -c 'import reflex'` -> **0** lines mentioning pydantic
  (importtime_bare.log); `sys.modules` contains no pydantic after import.
- dc_app fully functional in Chromium: initial render, dataclass field mutation,
  input-driven set, dict mutation, foreach over list[dataclass] + append, and an
  event handler with a **dataclass-hinted arg** receiving a dict payload from the
  frontend (exercises the exact `_transform_event_arg` path PR #6786 rewrote —
  the `BaseModelV2 = None` branch). No console errors, no 4xx/5xx, no pydantic
  tracebacks in the server log.
- Error UX without pydantic:
  - user app `import pydantic` -> plain `ModuleNotFoundError: No module named
    'pydantic'` (see test d).
  - `rx.session()` / `rx.Model()` -> clear: "Database is not available. Please
    install the required packages: `pip install reflex[db]`."
  - **`class Item(rx.Model, table=True)`** (the standard way to declare a table)
    -> `TypeError: Item.__init_subclass__() takes no keyword arguments` — no
    guidance at all. Confusing, but identical on 0.9.8 (sqlmodel was already
    optional there), so NOT a regression. Recorded as anomaly.
  - `rx.Base` does not exist in 0.9.8 or 0.9.9a1 (removed earlier; not part of
    this change).

### (b) `reflex[pydantic]==0.9.9a1` vs 0.9.8 — PASS, no regression
All 8 checks pass identically on 0.9.9a1 (dev + prod) and 0.9.8 (dev):
initial render of model fields, computed var `model_dump_json`, top-level field
mutation, nested-model mutation, list-in-model append, computed var after
mutations, `rx.foreach` over `list[Model]` + append, event arg
`model_validate` from frontend dict (`receive_user` renders `Grace:45:Paris:User`).
Prod mode (single port, `--env prod`) also passes with a fully clean console.

pydantic.v1-style models (`pydantic.v1.BaseModel`) are NOT supported as state
vars — `VarTypeError: State vars must be of a serializable type ... Found var
... with type V1M`, and `serializers.serialize()` returns None for them.
**Identical behavior on 0.9.8** -> not a regression; note the error message says
"pydantic models" are valid, which may confuse v1 users slightly.

### (c) `reflex[db]==0.9.9a1` — PASS
CRUD through the UI in Chromium: create 2 rows via form submit, rename first,
delete first, rows re-rendered via foreach from `rx.session` queries each time,
and data persists across a full page reload (sqlite file). No console errors.
Log shows `DeprecationWarning: reflex.Model has been deprecated in version
0.9.2 ... removed in 1.0.0` (expected; rx.Model itself is on the way out).

### (d) upgrade path — PASS
- venv with 0.9.8 ran pyd_app (baseline above), then
  `uv pip install -U --prerelease=allow reflex==0.9.9a1`: pydantic 2.13.4
  **remains installed** (upgrade doesn't remove it), and the same app dir re-runs
  on 0.9.9a1 with all 8 browser checks green.
- Clean 0.9.9a1 install running a pydantic-importing app: `reflex run` fails in
  **0.83 s** with a traceback ending `ModuleNotFoundError: No module named
  'pydantic'` at the user's own `import pydantic` line (bare_fail_run.log).
  Timing is immediate and the cause is identifiable, but there is no
  reflex-specific hint pointing at `pip install reflex[pydantic]`.
  (Repro: copy `pyd_app` dir, run with the bare venv.)

## Adjacent observations (not this cluster, recorded for completeness)

1. Prod build (`vite v8.2.0` rolldown) logs on every build, twice (client+ssr):
   `Warning: Invalid input options - For the "jsx". Invalid key: Expected never
   but received "jsx".` and `WARN advancedChunks option is deprecated, please
   use codeSplitting instead.` (pyd_prod_run.log). Cosmetic, but reflex is
   passing options its pinned vite/rolldown no longer accepts.
2. Dev server logs a Vite warning about `import "./vite-plugin-safari-cachebust"
   without a file extension` in the framework-generated `vite.config.js`
   (suppressible via VITE_CONFIG_NATIVE_IGNORE_WARNING).
3. `DeprecationWarning: Implicit Radix Themes enablement has been deprecated`
   appears for blank-template apps on 0.9.9a1.
4. `reflex.__version__` does not exist (`AttributeError: No reflex attribute
   __version__` via the lazy loader) — minor DX papercut when checking versions.
5. Env-only: bun installs are OOM/network fragile on this shared box; see the
   NO_PROXY note above (three "Installing frontend development dependencies
   failed" launches were environmental, exit -9 / ConnectionClosed).

## Screenshots / logs kept here

`dc_bare_{initial,final}.png`, `pyd_099_{initial,final}.png`,
`pyd_098_{initial,final}.png`, `pyd_upgraded_{initial,final}.png`,
`pyd_prod_{initial,final}.png`, `db_099_{initial,final}.png`,
`bare_fail_run.log` (clean-install ModuleNotFoundError), `importtime_bare.log`.
