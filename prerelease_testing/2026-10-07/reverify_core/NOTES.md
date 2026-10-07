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

### 4. Enterprise AG Grid demo (F-001 enterprise half) — dev 3107/8107, prod 3108
Venv `reverify_core-ent` = the shared `alpha2-ent` freeze (reflex 0.10.0a2 + offline `reflex_enterprise-0.9.7a4` wheel
`[mcp]`) **plus greenlet and the demo's own deps (faker, aiosqlite, pandas==2.2.3)** — `logs/freeze-reverify_core-ent.txt`
(diff vs `freeze-alpha2-ent.txt`: only those additions). All AG Grid runs used this venv, so none of them ever hit the
greenlet ImportError (N-001); the shared `alpha2-ent` got greenlet from the orchestrator later but still lacks faker,
which the demo imports, so it cannot run this demo unmodified. App = the 10-06 explorer's copy
(`/home/user/reflex/prerelease_testing/2026-10-06/ent_demos/partial/ag_grid`, incl. `qa_extras.py`), fresh sqlite via
`REFLEX_DB_URL=sqlite:///reflex.db reflex db migrate` (note: `DB_URL` without prefix is ignored → "No database url configured").
```bash
cd ag_grid && CI=true REFLEX_DB_URL=sqlite:///reflex.db $SB/envs/reverify_core-ent/bin/reflex db migrate
CI=true REFLEX_DB_URL=sqlite:///reflex.db PIDTAG=ent bin/start_app.sh reverify_core-ent <copy>/ag_grid 3107 8107 logs/x.log --loglevel debug
CI=true REFLEX_DB_URL=sqlite:///reflex.db REFLEX_API_URL=http://localhost:3108 PIDTAG=ent bin/start_app.sh reverify_core-ent <copy>/ag_grid 3108 3108 logs/y.log --env prod
cd ent_scripts   # qa_common.py patched to read the pidfile from $QA_PIDFILE or $SB/apps/reverify_core/pids/ent.pid
QA_INFINITE_ROUTE=/qa-model-workaround $D drive_ag_model.py http://localhost:3107 <out> reverify_core-ent <copy>/ag_grid/reflex.db ssrm,workaround,simple,auth
$D smoke_routes.py http://localhost:3107 <out> ag_grid-smoke reverify_core-ent / /model /model-auth /model-ssrm ...   # all 20 routes
$D probe_infinite.py http://localhost:3107 /qa-model-workaround <copy>/ag_grid/reflex.db <out>.json   # paging + filter
```
- **`/model` and `/model-auth`: data endpoint 200, grid shows db rows, in dev and prod; zero
  `'Field' object has no attribute 'from_request'` in any server log** (a1: every request 500'd). F-001 enterprise half fixed.
- `/model-ssrm`: logged-out request + no rows, Generate Friends (+50 rows in sqlite), login survives reload, sort
  asc/desc vs db min/max, filterModel sent, cell edit → sqlite, selection → `selected_items` badges, advanced filter,
  logout empties grid — all pass in dev (warm run) and prod. First dev run timed out waiting for rows (first page
  compile under load); a focused probe (`probe_ssrm.py`) and the rerun pass.
- Infinite (`/model`, `/qa-model-workaround`): data rows, sort vs db, numeric edit → sqlite, multi-row delete → sqlite,
  block paging by scrolling (rows 0-145, requests `0-50`, `100-150`, all 200) pass.
- Failing checks, all **pre-existing** (identical on reflex 0.9.12 + the same offline enterprise wheel,
  venv `reverify_core-entmixed`, `out/ag_infinite/mixed-dev-*.json`, or in the 10-06 mixed prod log):
  `filtered rows all match and count matches db` / `infinite: text filter matches db` — the filter works (filterModel
  sent, the 1 matching row rendered) but AG Grid keeps empty placeholder rows that the driver counts;
  `add dialog inserts row` — server `TypeError: SQLite DateTime type only accepts Python datetime and date objects`
  for the `met` string (also in 10-06 `ag_grid-prod-mixed.log`).
- Smoke: 20/20 routes, 0 console errors, 0 http errors in dev and prod; 1 AG Grid warning #129 (headerCheckbox with
  infinite model) on `/model-auth` (demo config). Dev-only React warning `<tr> cannot be a child of <table>` in the
  ModelWrapper add-row dialog (same on 0.10.0a1; not reached on 0.9.12 earlier). Prod logs 20×
  `Warning: Page <x> is being redefined with the same component.` — identical on the 10-06 0.9.12 mixed prod run.

### 5. Third-party packages (venv `reverify_core-tp` = alpha2 freeze + the 10-06 `packages.txt` + authlib + greenlet + matplotlib)
- `scripts/clerk_probe.py` (`logs/clerk_probe.txt`): reflex-clerk 1.0.3 is still broken on 0.10 (class reads return
  `Field`, so `clerk_provider()` without a secret key no longer raises and `jwt_public_keys` is a `Field`). **Changed by
  #7461:** after `clerk_provider(secret_key="sk_test_123")`, `ClerkState.secret_key` is now
  `Field(default='sk_test_123')` (0.10.0a1: the raw `'sk_test_123'` because the assignment replaced the descriptor;
  0.9.12: `'sk_test_123'`), so the package's server-side Clerk client would get a `Field` as bearer token. Fails closed.
- `scripts/derive_a_dynoselect.py` (`logs/dynoselect_probe.txt`): unchanged from a1 — `VarTypeError: Unsupported Operand
  type(s) for []: ObjectCastedVar, Field` at `dynoselect.py:172` (before it reaches `State._raw_options = options`);
  0.9.12 fails earlier for other reasons. `/dynoselect` page in Chromium shows the same error text.
- **F-018** (`tp_components` `/clerk`, dev 3109/8109, React 19.3.0, `logs/f018_clerk_alpha2_dev.txt`): 2/2 loads log
  `Encountered a script tag while rendering React component` once, alongside the package's own route failure
  `SyntaxError: The requested module '/utils/state.js' does not provide an export named 'Event'`. Still present.
```bash
PIDTAG=tp bin/start_app.sh reverify_core-tp <copy>/tp_components 3109 8109 logs/x.log --loglevel debug
$D drivers/debug_page.py http://localhost:3109/clerk 6000 out/tp/clerk.png
```

### 6. Benign / informational
- `Compiling: ... 23/22` progress counter over-counts by one in every run — also on 0.9.12 (`19/18`).
- granian warns "Configured number of workers appears to be higher than the amount of CPU cores" in prod (6 workers on 4 CPUs).
- chromium background connections to google.com rejected by the proxy (environment).

## Before/after the orchestrator's greenlet change (07:0x UTC)
Everything in this cluster that touches `rx.Model` ran in my own venvs that already had greenlet
(`reverify_core-a2db-gl`, `reverify_core-ent`, `reverify_core-tp`); the shared `alpha2` was only used for code paths that
do not import `reflex.model` (derive_* probes except F-013, core_a2, classattr, fwdref, typing). The greenlet ImportError
itself is the orchestrator's N-001 and is not re-reported here (evidence kept in `greenlet/` and `logs/greenlet*`).
Self-made venvs: reverify_core-a2db (fresh reflex[db]==0.10.0a2, no greenlet — evidence only), reverify_core-s912db
(fresh reflex[db]==0.9.12, no greenlet — evidence only), reverify_core-a2db-gl, reverify_core-ent, reverify_core-entmixed
(0.9.12 + offline enterprise wheel + greenlet + demo deps), reverify_core-tp, reverify_core-ty (ty 0.0.85).

## Re-verification verdicts
| id | verdict | evidence |
|---|---|---|
| F-001 core | **changed** (semantics kept and now documented; silent UI corruption replaced by loud errors) | `derive_a.txt` unchanged a1→a2 except `f"{S._x}"` → `BackendVarFormatError`; unchanged e2e app now fails compile/export at `classattr_app.py:57` in dev and prod |
| F-001 enterprise | **fixed** | `/model`, `/model-auth` 200 + rows dev/prod, 0 `from_request` errors (`out/ag_grid_*_a2*/`, `logs/ag_grid-*-a2ent*.full.log`) |
| F-004 | **fixed** | `derive_b*.txt` (descriptor kept, pickle/reset/dev writes OK), e2e `/` dev + prod/redis (`core-alpha2-*.json`) |
| F-011 | still broken | `logs/f011_fwdref.txt` |
| F-012 | still broken | `logs/derive_c.txt` |
| F-013 | still broken | `logs/derive_d_a2gl.txt` (pydantic `_model_construction.py:156`) |
| F-014 | still broken | `logs/f014_component.txt` |
| F-016 | still broken (also with ty 0.0.85) | `logs/f016_typing.txt` |
| F-018 | still broken (cosmetic) | `logs/f018_clerk_alpha2_dev.txt` |

## Issues (new on 0.10.0a2)

### I-1 (medium, regression vs 0.10.0a1): state saved by 0.10.0a2 is discarded by 0.9.12 / 0.10.0a1 workers
#7461 removed defaults from the schema hash; older releases compare only against their default-including hash, so
every state an a2 worker saves is a `StateSchemaMismatchError` for them and the redis manager silently creates a fresh
state. A rolling deploy (old + new workers on one Redis) or a rollback from 0.10.0a2 to 0.9.12 logs users out / loses
session state. 0.10.0a1-saved state still loads on 0.9.12 (its CHANGELOG #7312 promises exactly this:
"States saved by this release still load in workers of the previous one, so rolling deploys sharing Redis keep
working"); the a2 CHANGELOG only says states "saved by this release or later" stay loadable.
Repro (Python, 10 s): `cd scripts/schema; SCHEMA_DEFAULT=0 $SB/envs/alpha2/bin/python derive_h_schema.py alpha2 save $SB/apps/rc/s.bin;
SCHEMA_DEFAULT=0 $SB/envs/stable/bin/python derive_h_schema.py stable load $SB/apps/rc/s.bin` → `StateSchemaMismatchError`
(a1-saved file loads). E2E: section 3 above (`out/core/rb2-x-p2.json`: count 5 "fresh" vs control `ctl4-a1-p2.json` 42).

### I-2 (medium, new-feature gap): assigning a plain default to a browser-storage var silently drops its storage
`St.ls = "x"` / `St.ck = "x"` (declared `str = rx.LocalStorage(..., name=...)` / `rx.Cookie(...)`), a factory returning a
plain value, or the documented ComponentState pattern `cls.value = initial` turn the var into an ordinary frontend
var: no localStorage key / cookie is written, the value is not restored in a new tab, no warning. The #7461 entry says
"Browser storage vars keep their storage settings when a factory is assigned"; only factories/values that themselves
produce an `rx.LocalStorage(...)` keep it. Workaround: assign `rx.LocalStorage("x", name=...)` again.
0.9.12 ignored the class assignment (storage kept, default not applied); its documented
`cls.__fields__[n].default = v` also drops storage (`logs/derive_i_storage_legacy.txt`).
Repro: `derive_g_assign.py alpha2` (storage section), `derive_i_storage_legacy.py alpha2`; e2e `/storage` page,
`out/core/core-alpha2-{dev,prod-redis}.json` (`1_browser_storage` lacks `ls_plain_key`, `lscs_key`, `ck_key`; `2_new_tab_same_browser` shows defaults).

### I-3 (low): #7456 leaves silent paths and some non-actionable errors
`str(State._x)`, `"%s" % State._x` and `f"{State._x!s}"` still embed `Field(default=..., ...)` into the page;
`rx.box(id=State._x)` raises `TypeError: expected string or bytes-like object, got 'Field'` (no var name); the
`BackendVarFormatError` text ("Use a regular state var instead.") does not mention the documented
`State._x.default_value()` or `ClassVar`. Repro: `derive_e_format.py alpha2`.

### I-4 (low, docs): the documented `State._items.default_value()` is not portable to 0.9.x
On 0.9.12 the class attribute is the raw value → `AttributeError: 'list' object has no attribute 'default_value'`.
`State.get_fields()["_items"].default_value()` works on 0.9.12, 0.10.0a1 and 0.10.0a2 (and `ClassVar` for constants).
Repro: `derive_e_format.py stable` ("documented fix" section), `derive_workarounds.py <v>`.

### I-5 (low): #7465 dev guard accepts any undeclared `_x__y` name
`self._sneaky__name = 1` (never declared, single leading underscore) no longer raises `SetUndefinedStateVarError` in dev
(0.9.12 and 0.10.0a1 raise); the guard now exempts every `_`-prefixed name containing `__`. Repro: `derive_f_dunder.py alpha2` (REFLEX_ENV_MODE=dev).

### I-6 (low, docs): class-default assignment scope is surprising and undocumented in two cases
(a) Assigning on a mixin (`Mx.mv = 7`) only affects states that include the mixin **afterwards**; states created
earlier keep the old default (`derive_g_assign.py`, mixin section). (b) A runtime assignment (`type(self).count = 77`
in a handler) changes only the worker process that ran it: with 6 prod workers a new session got 20, in dev 77
(`out/core/core-alpha2-{dev,prod-redis}.json` `cs.6_new_session_tab2`).
