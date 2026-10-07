# Cluster `reverify_core` — re-verification of F-001/004/011/012/013/014/016/018 on reflex 0.10.0a2 (2026-10-07)

Versions under test: **reflex / reflex-base 0.10.0a2** (shared venv `$SB/envs/alpha2`, py3.12, pydantic 2.13.5,
sqlalchemy 2.1.3, sqlmodel 0.0.48) and **reflex-enterprise 0.9.7a4 offline wheel** (`$SB/envs/alpha2-ent`).
Before/after: `$SB/envs/alpha` (0.10.0a1) and `$SB/envs/stable` (0.9.12). Everything installed from PyPI
(plus the offline enterprise wheel); nothing from the checkouts; every script asserts the venv it runs in.

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
D=/home/user/reflex/prerelease_testing/2026-10-07/reverify_core   # this directory
mkdir -p $SB/apps/rc && cp -r $D/scripts/. $SB/apps/rc/ && cd $SB/apps/rc     # never run from inside the checkout
export REFLEX_TELEMETRY_ENABLED=false
```
Ports used: frontend 3100-3119, backend 8100-8119 (prod: one port), redis on 8119.

## Python-level re-verification (scripts/, logs/)
Each script takes the venv name as argv[1]; run with `REFLEX_ENV_MODE=dev|prod` where the mode matters:
```bash
for v in alpha2 alpha stable; do for m in dev prod; do REFLEX_ENV_MODE=$m $SB/envs/$v/bin/python derive_a.py $v; done; done
#   same loop for derive_b.py derive_b_reset.py derive_workarounds.py derive_f_dunder.py derive_g_assign.py
$SB/envs/<v>/bin/python derive_e_format.py <v>     # #7456 formatting / child / prop paths
$SB/envs/<v>/bin/python derive_c.py <v>            # F-012
cd derive_d && $SB/envs/<v>/bin/python -u derive_d.py <v> <direct|exec|model_here|model_import|both_models|memo|env>   # F-013
cd schema && SCHEMA_DEFAULT=<n> $SB/envs/<v>/bin/python derive_h_schema.py <v> save|load <file>   # saved-state schema matrix
```

### Results (Python level)

| check | 0.10.0a2 | 0.10.0a1 | 0.9.12 | log |
|---|---|---|---|---|
| F-001 class read of backend var (`S._x`, mixin, inherited, `cls.`/`type(self).`) | `Field` (kept, now documented) | `Field` | value | `logs/derive_a.txt` |
| #7456 `f"{S._size}px"`, `"{}".format(S._size)`, `format()` | **`BackendVarFormatError`** (subclass of `VarTypeError`), names `'S._size'` | silent Field repr | `'16px'` | `logs/derive_e_format.txt` |
| #7456 `str(S._size)+"px"`, `"%s" % S._size`, `f"{S._size!s}"` | **still silently embeds `Field(default=16, ...)`** | same | value | same |
| child `rx.text(S._label)` | `ChildrenTypeError` (names the Field repr) | same | renders | same |
| prop `rx.box(width=S._size)`, `style=`, `rx.foreach`, `rx.cond`, `rx.match`, `rx.Var.create`, `rx.console_log` | `TypeError: Unsupported type <class '...Field'> for LiteralVar. Tried to create a LiteralVar from Field(...)` | same | works | same |
| typed props: `rx.icon(size=)`, `rx.link(href=)`, `class_name=[...]` | `TypeError: Invalid var passed for prop ...` (component-specific wording) | same | works | same |
| `rx.box(id=S._label)` | `TypeError: expected string or bytes-like object, got 'Field'` (cryptic, no var name) | same | works | same |
| event arg `S.handler(S._label)` | `EventHandlerTypeError` (clear) | same | works | same |
| documented fix `S._items.default_value()` | works (`["a","b"]`, fresh copy per call) | works | **AttributeError** (`list` has no `default_value`) — not portable; `S.get_fields()["_items"].default_value()` works on all three | same |
| error message wording | "Backend var 'S._size' exists only on the server ... Use a regular state var instead." — does **not** mention `.default_value()` or `ClassVar` | n/a | n/a | same |
| F-004 `Cfg._key = "sk"` then fresh/pickled/same instance | `'sk'` everywhere; descriptor kept; dirty-tracked writes; `reset()` restores `'sk'` (dev+prod) | `'sk'`→`None` after pickle; dev write/reset raise | `None` everywhere | `logs/derive_b*.txt` |
| #7461 frontend var `A.count = 10` | stays a Var (UI reactive), fresh 10, `dict(initial=True)` 10, computed var 20 | int replaces Var | int replaces Var (UI static 10, instances 0) | `logs/derive_g_assign.txt` |
| #7461 wrong type / Literal / list[int] / dict[str,int] / backend `str|None`=5 | `TypeError: Invalid default for field 'x': expected ..., got ... of type ...`; previous default kept | silently accepted | ignored | same |
| #7461 `rx.field(5)` / `rx.Var.create(5)` / `Other.o` / own Field | `TypeError` "A Field cannot overwrite another field..." / "A Var cannot be a field default. Use ClassVar[rx.Var]..." | accepted (breaks state) | ignored | same |
| #7461 zero-arg factory | called once at assignment, then per instance/reset; mutations don't leak; raising / wrong-type factory → `TypeError`, previous default kept; 1-arg callable → "Default factory ... failed: missing 1 required positional argument"; `Any`/`Callable` annotations store the callable itself | n/a | n/a | same |
| #7461 MutableProxy assigned as default | unwrapped to `list` | | | same |
| #7461 inherited var `C1.pv = 5` | changes `P` and sibling `C2` too (documented) | | ignored | same |
| #7461 mixin `Mx.mv = 7` after `U1`/`U2` were created | only states created **afterwards** see 7; `U1.mv = 5` affects U1 only | | ignored | same |
| #7461 storage: factory returning `rx.LocalStorage(...)` | keeps classification, compiled with the factory's name/options | | ignored | same |
| #7461 storage: declared `rx.field(default_factory=lambda: rx.LocalStorage(...name=...))` | compiled with `{'name': 'decl_fac_key', 'sync': True}` | | compiled `{'sync': False}` (name lost) | same |
| #7461 storage: **plain value** (`St.ls_plain = "x"`, `St.ck = "x"`) or **factory returning a plain str** | **var silently stops being browser storage** (`_is_client_storage` False, absent from compiled storage) | | still storage (assignment ignored) | same |
| #7465 `__counter = 0`, annotated `__ann: int = 5`, dunders, `__data_source_params_class__` | plain class attributes (class read = value, not in `get_fields()`); `.from_request` works | fields (`Field`), enterprise-style dunder → `AttributeError 'Field' ... from_request` | plain | `logs/derive_f_dunder.txt` |
| #7465 writes from mixin (`_Mx__mx`), base (`_Base2__from_base`), `_Under` class (dev) | allowed | base write raises in dev | mixin & base writes raise (dev and prod) | same |
| #7465 `__fielded: rx.Field[int] = rx.field(0)` | real backend var: dirty-tracked, computed var reacts, pickles, resets, class assignment keeps descriptor | field | field but **not** dirty-tracked | same |
| #7465 plain dunder: pickle / reset | survives pickle (instance dict); **not** reset by `reset()` (same as 0.9.12) | reset (field) | not reset | same |
| #7465 dev typo guard | `self._sneaky__name = 1` (undeclared, any `_x__y` name) now accepted silently | raises | raises | same |
| saved-state schema: a2 save → a2 load with changed default | **loads** | a1→a1 changed default: mismatch | 0.9.12 same: mismatch | `logs/derive_h_schema.txt` |
| a1 / 0.9.12 saved → a2 (same default) | loads (legacy schema accepted) | | | same |
| **a2 saved → a1 / 0.9.12 (same default)** | **`StateSchemaMismatchError`** → older workers discard the session | a1 saved → 0.9.12: loads | | same |
| F-012 `PageContext.get()` | `LookupError: <ContextVar name='PageContext' at 0x...>` (unchanged) | same | `RuntimeError: No active PageContext ...` | `logs/derive_c.txt` |
| F-013 rx.Model deprecation location | `(.../pydantic/_internal/_model_construction.py:156)` (unchanged; needs greenlet venv, see below) | same | `(<frozen abc>:106)` | `logs/derive_d_a2gl.txt` |
| F-014 `reflex component --help` | `Error: No such command 'component'. Did you mean 'compile'?` rc=2 (unchanged) | same | works | `logs/f014_component.txt` |
| F-011 fwdref_app `reflex compile --dry` | `TypeError: Unsupported type ForwardRef('list[Item]') for guess_type.` (unchanged) | same | `NameError: name 'Item' is not defined` | `logs/f011_fwdref.txt` |
| F-016 ty 0.0.84 **and 0.0.85** / pyright 1.1.414 | ty: 62,68,75,80,88,89,98,99; pyright: 62,68,80,88,89,98,99 (unchanged) | identical | ty also 76–79 | `logs/f016_typing.txt` |

### NEW: fresh `reflex[db]` installs cannot use `rx.Model` (greenlet)
`sqlmodel 0.0.48` (PyPI 2026-10-06 21:44 UTC) allows SQLAlchemy 2.1 (2.1.3, 2026-10-03), which no longer installs
`greenlet`. `reflex/model.py:69` imports `sqlalchemy.ext.asyncio` at module import, so the first access to
`rx.Model`, `rx.session`, `rx.ModelRegistry` or `import reflex.model` raises
`ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed ...`, and
`reflex db init` crashes. Reproduced on fresh `reflex[db]==0.10.0a2` **and** fresh `reflex[db]==0.9.12`, and on the
shared `$SB/envs/alpha2` / `alpha2-ent` venvs; `alpha`/`stable` (SA 2.0.54 + greenlet) are fine; adding `greenlet` fixes it.
```bash
cd $SB && uv --no-config venv --python 3.12 $SB/envs/reverify_core-a2db
uv --no-config pip install --python $SB/envs/reverify_core-a2db/bin/python --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14'
cd greenlet && $SB/envs/reverify_core-a2db/bin/python gl_probe.py reverify_core-a2db      # rx.Model ImportError
cd greenlet/dbapp && $SB/envs/reverify_core-a2db/bin/reflex db init                    # rc=1, same ImportError
# same with 'reflex[db]==0.9.12' (venv reverify_core-s912db); + greenlet (venv reverify_core-a2db-gl): rc=0
```
Logs: `logs/greenlet_probe.txt`, `logs/greenlet-dbinit-*.log`, `logs/freeze-reverify_core-*.txt`.
Consequence for this cluster: F-013 and the enterprise AG Grid demo (uses `rx.Model`) were run in my own venvs
`reverify_core-a2db-gl` / `reverify_core-ent` (= alpha2(-ent) graph + greenlet; `logs/freeze-reverify_core-ent.txt`).

## End-to-end (real server + Chromium)

Helpers: `bin/start_app.sh <venv> <app_dir> <FP> <BP> <log> [reflex run args]` (setsid; pidfile `pids/$PIDTAG.pid`),
`bin/wait_up.sh <url> <secs> <pidfile>`, `bin/stop_app.sh <pidfile>` (kills the process group), `bin/ports.py`.
Driver: `drivers/drive_core.py <base> <outdir> <label> [home,cs,storage,dunder | schema1 | schema2]`
(run as `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python ...`).
App: `core_a2/` (pages `/` F-001/F-004 adapted e2e app, `/cs` #7461 ComponentState, `/storage` #7461 storage,
`/dunder` #7465, `/schema`). Env knobs: `CORE_PAGES` (subset of pages; 0.9.12/0.10.0a1 can only build
`home,dunder,schema`), `CORE_ASSIGN_STORAGE=0` (skip storage class assignments for old versions), `CORE_DEFAULT`
(default of `Sch.count`), `CORE_API_URL` (prod single port).

```bash
cp -r core_a2 $SB/apps/rc/run_dev   # always run from a copy
PIDTAG=core bin/start_app.sh alpha2 $SB/apps/rc/run_dev 3101 8101 logs/x.log --loglevel debug          # dev (disk manager)
redis-server --port 8119 --save '' --appendonly no &
CORE_API_URL=http://localhost:3104 REFLEX_REDIS_URL=redis://localhost:8119 PIDTAG=core \
  bin/start_app.sh alpha2 $SB/apps/rc/run_prod 3104 3104 logs/y.log --env prod --loglevel debug          # prod + redis
# baselines: venv alpha / stable with CORE_PAGES=home,dunder,schema CORE_ASSIGN_STORAGE=0
```

### 1. Unchanged 10-06 e2e app (`e2e_classattr/`) — dev 3100/8100 and prod 3110
Both modes now fail at compile/export (server exits) with
`BackendVarFormatError: Backend var 'ConstState._LABEL' exists only on the server and has no frontend value, so it
cannot be used in the UI. Use a regular state var instead.` + `Happened while evaluating page 'index'`, traceback
pointing at `classattr_app.py:57` (`rx.text(f"label={ConstState._LABEL}")`). On 0.10.0a1 the same app rendered
`label=Field(default=...)` silently. Logs: `logs/e2e-classattr-asis-alpha2-{dev,prod}.full.log`.

### 2. `core_a2` on alpha2 — dev (3101/8101) and prod+redis (3104)
Results: `out/core/core-alpha2-dev.json`, `out/core/core-alpha2-prod-redis.json` (+ screenshots).
- `/` (adapted e2e app, `default_value()` style): `label=label-const`, width 16px, foreach items, ClassVar label,
  ComponentState button `+5`; **F-004 e2e fixed**: `show` → `key='sk_live'`, still `'sk_live'` 3.5 s later (debounced
  disk save / redis reload no longer flips it), `set_instance` → `'set-on-instance'`, `reset` works and restores
  `'sk_live'`, survives reload; no server traceback. Dev and prod identical.
  Baselines (`core-alpha-dev.json`, `core-alpha-prod-redis.json`, `core-stable-dev.json`, `core-stable-prod-redis.json`):
  0.10.0a1 flips to `None` after 3.5 s and raises `SetUndefinedStateVarError` on set_instance/reset in dev; 0.9.12 always `None`.
- `/cs`: `Ctr.create(start=10)` / `(start=20)` → 10/20, labels lbl10/lbl20, tags init10/init20, backend `_hidden`
  1000/2000 (+1 per click → `hidden=1001`/`2001`); `reset` restores 10 (the LAST configured default — get_component
  assigns 1 then `start`); handler doing `type(self).count = 77; self.reset()` → 77; same-session reload keeps values;
  new session (tab 2) after the runtime reconfigure: **dev 77, prod 20** (prod runs 6 granian workers; a runtime class
  assignment only changes the worker process that ran it — expected but undocumented). The docs' verbatim
  `EditableText` example works (initial values "Click to edit" / "Edit me!" / "Reflex is fun", editing works).
- `/storage`: factory returning `rx.LocalStorage(name="ls_fac_key2", sync=True)` → localStorage key `ls_fac_key2`
  written and read back in a new tab; declared factory → `decl_fac_key` works; `reset` writes defaults back.
  **Plain-value assignments lose browser storage**: `St.ls_plain = "assigned-plain"`, `St.ck = "assigned-ck"` and the
  ComponentState `LsCS` configured the documented way (`cls.value = initial` with `value: str = rx.LocalStorage(..., name="lscs_key")`)
  show the assigned default, but after `change all` **no `ls_plain_key` / `lscs_key` localStorage entry and no
  `ck_key` cookie is written**, and a new tab shows the defaults again (dev and prod identical).
- `/dunder`: `bump` (plain `__counter`) updates `view` but the computed var reading it stays 0 (documented "vars do not
  react"; same on 0.9.12, a1 reacted); `bump_silent` ×2: dev keeps the value in memory (`counter=3`), prod+redis
  loses it (`counter=1`) because a plain-attribute-only change does not mark the state touched — **same as 0.9.12
  prod+redis**; `__fielded` (rx.field) computed var reacts; mixin `__mx` writes work (0.9.12 raised
  `SetUndefinedStateVarError` in dev and prod); `__data_source_params_class__.from_request` works.
- Console: only benign lines + `/favicon.ico` 404 (prod); no page errors; no server tracebacks.

### 3. "Defaults are no longer part of the saved-state schema" (`/schema`)
`reflex run` deletes `.states/` at startup ("Resetting disk state manager"), so with the default disk manager only a
hot reload can carry state across a source change (pre-existing; not a finding).
- dev hot reload (edit the default `"0"`→`"5"` in source while the tab's token is resumed): **alpha2 keeps `42`**
  (`out/core/hr-alpha2-dev-p2.json`); **0.10.0a1 resets to the new default 5** (`hr-alpha-dev-p2.json`).
- prod + redis restart with `CORE_DEFAULT=0` → `5`: alpha2 keeps `42` (`core-alpha2-prod-p2.json`).
- **Rollback / mixed fleet** (prod + the same redis, same token, identical default 5 throughout):
  0.9.12 → 0.9.12 restart keeps 42 (`ctl3-stable-p2.json`); 0.10.0a1 → 0.9.12 keeps 42 (`ctl4-a1-p2.json`, the a1
  changelog promise); **0.10.0a2 → 0.9.12 loses the session: count 5 / note "fresh"** (`rb2-x-p2.json`,
  `rollback-stable-p2.json`). Mechanism: a2 pickles `(new_schema_hash, state)`; 0.9.12/a1 compare only against their
  default-including hash → `StateSchemaMismatchError` → `contextlib.suppress` in `istate/manager/redis.py` → fresh state.
Rerun:
```bash
# phase 1 (any venv/port), then restart the server (or another version on the same redis), then phase 2 with the SAME label prefix
$D drivers/drive_core.py http://localhost:3104 out/core rb-x-p1 schema1   # writes out/core/rb-x-token.txt
$D drivers/drive_core.py http://localhost:3105 out/core rb-x-p2 schema2   # resumes that token in a new context
```
