# class_state fixtures — the state class model (class reads/writes, field defaults, #7516 / #7519, state-store compatibility)

What this area re-verifies: class-level reads of state vars (F-001: a class read returns a `Field`), class assignment and
class patching of a var (F-004 / N-039 / N-040 / A3-01 / A3-02 / A3-04 / N-005: now a `TypeError` naming the declaring
state; defaults are changed through `State.__fields__[name].set_default(...)` and tests patch the field), the #7519
copy-at-definition behaviour (A5-01 … A5-05), the error message's owner naming, `add_var` / auto-setter collisions
(A4-01, A4-02), the dev guard for name-mangled attributes (N-008), `BackendVarFormatError` (N-006), background tasks
writing inherited vars / calling inherited handlers (N-024, A3-06), state-store compatibility across versions (N-004),
dev hot reload of a state file, AppHarness with two apps, docs samples, and downstream reach (greps + third-party states).

Sources: the a5 pass (`a5_class_state`, `verify_class_state5`), a4 (`a4_class_state`, `verify_class_state`), a3
(`a3_class_state`, `a3_events_tp` n024doc), and the a2 pass (`reverify_core` derive_* scripts and N-004 fleet app,
`thirdparty_a2` pytest probes). Every fixture is the newest copy; superseded ones were dropped (list at the end).

## Setup

```bash
CS=/path/to/this/dir                      # read-only; never run python from inside a reflex checkout/worktree
export SB=/tmp/.../scratchpad             # scratch root; default in env.sh
mkdir -p $SB/apps/class_state && cp -r $CS $SB/apps/class_state/src && CS=$SB/apps/class_state/src   # run from a copy
bash $CS/build_venvs.sh class_state-new <reflex version under test>     # + UV_PRERELEASE=allow for an alpha/rc
bash $CS/build_venvs.sh class_state-prev 0.10.0                          # previous release, same test deps
bash $CS/build_venvs.sh class_state-tp <version> 3.12 tp                 # optional: + downstream/packages.txt (22 third-party pkgs)
export NEW=class_state-new PREV=class_state-prev   # venv NAMES under $SB/envs; CTRL=<venv> for a positive control
```
`env.sh` (sourced by every `bin/` script) requires `SB` and sets `NEW` (default `class_state-new`), `PREV` (default
`class_state-prev`; both built with `build_venvs.sh` as above), `CTRL`, `DRIVER` (playwright venv, default `driver`), `FP`/`BP`
(3300/8300), `REDIS_PORT` (8309), `W` (work dir, default `$SB/apps/class_state`: pids, logs, out, app copies) and
`REFLEX_TELEMETRY_ENABLED=false`. Python probes guard the venv with `assert f"/envs/{EXPECT_VENV}/" in reflex.__file__`;
`bin/start_app.sh` exports `EXPECT_VENV` for the app guards. Chromium: `CHROMIUM` (default `/opt/pw-browsers/chromium`).

**Ports:** frontend 3300-3339, backend 8300-8339, redis 8309 (`bin/start_app.sh` refuses other ports; override with
`PORT_LO_F/PORT_HI_F/PORT_LO_B/PORT_HI_B`). Used: 3300/8300 dev, 3301 prod+Redis, 3302/8302 lateapp/dynhook/n024doc,
3303 N-004 Redis chain, 3305/3306 + 8305/8306 AppHarness, 3307 N-004 fleet. One server set at a time.

**Venvs:** `$NEW`/`$PREV` built by `build_venvs.sh` (reflex[db,testing] + pytest, pytest-mock, pytest-asyncio, numpy,
pandas, playwright 1.63.0); `$SB/envs/$DRIVER` (playwright) for browser drivers; a `tp` venv for the downstream tests.

## How to run the whole area (≈ 45 min)
```bash
. $CS/env.sh
bash $CS/bin/run_python_suite.sh $NEW; bash $CS/bin/run_python_suite.sh $PREV   # ~4 min each; $W/logs/py/<venv>/{summary,rc}.txt
diff <(cut -c1-28 $W/logs/py/$PREV/rc.txt) <(cut -c1-28 $W/logs/py/$NEW/rc.txt)  # then diff individual logs PREV vs NEW
bash $CS/bin/n004_matrix.sh $W/logs/n004 $NEW $PREV                              # N-004 Python-level interchange + schema hashes
# e2e (dev): app cse2e + hot reload
cp -r $CS/apps/cse2e $W/run/cse2e-dev && PIDTAG=dev $CS/bin/start_app.sh $NEW $W/run/cse2e-dev 3300 8300 $W/logs/cse2e-dev.log --loglevel debug
$CS/bin/wait_up.sh http://localhost:3300/ 400 $W/pids/dev.pid
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/$DRIVER/bin/python $CS/bin/drive_cse2e.py http://localhost:3300 $W/out/cse2e-dev.json
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/$DRIVER/bin/python $CS/bin/hot_reload.py $W/run/cse2e-dev $W/logs/cse2e-dev.log http://localhost:3300 $W/out/hot_reload.json
$CS/bin/stop_app.sh $W/pids/dev.pid
# e2e prod + Redis (9 workers): redis-server --port 8309 --save '' --appendonly no &  then
cp -r $CS/apps/cse2e $W/run/cse2e-prod && CSE2E_API_URL=http://localhost:3301 REFLEX_REDIS_URL=redis://localhost:8309 PIDTAG=prod \
  $CS/bin/start_app.sh $NEW $W/run/cse2e-prod 3301 3301 $W/logs/cse2e-prod.log --env prod   # wait_up, drive_cse2e.py http://localhost:3301 ..., stop_app
bash $CS/bin/n004_redis_chain.sh                    # PREV -> NEW -> PREV -> NEW on one token (prod, 3303, starts redis if needed)
# AppHarness, lateapp, badassign5, dynhook, n024doc, fleet: see the table
```
Expected results below are for **reflex 0.10.0** (from the a5 pass records unless marked **[re-validated 0.10.0]**).
For the next version, the interesting output is any line that differs from `$PREV`.

## Fixtures

All Python commands: `cd <dir of the file> && EXPECT_VENV=$NEW $SB/envs/$NEW/bin/python -I <file>` (pytest: `... -I -m pytest -p no:cacheprovider -p no:randomly -rA -q <file>`).
`bin/run_python_suite.sh` runs every row marked (S) with the right cwd/args.

### #7519: copy at definition, non-copyable and large defaults, owner message, docs (A5-01 … A5-05)
| path | exercises | findings | expected on 0.10.0 |
|---|---|---|---|
| `probes/probe_copydef.py` (S) | rows a1-a10, b, e1-e14: mutable class-body defaults filled after the class, non-copyable defaults, shapes | A5-01, A5-02/03 | **[re-validated 0.10.0]** output identical to a5: a1 `[]`, a2 `{}`, a5 `{}`, a8 `[]`, a9/a10/e14 snapshot; `rx.field(LATE)` (a3/a4) live. 0.9.12/0.10.0a4 were live. 0.10.0 documents the snapshot as a breaking change, so this is now *expected* behaviour |
| `probes/probe_copydef_extra.py` (S) | `add_var` late default, ComponentState.create cost with a large default | A5-01, A5-04 | **[re-validated]** `add_var` default snapshotted; 100× create ≈ 100 ms |
| `probes/v1/probe_v1.py` (+ `v1/pkg/`) (S) | real class statements across 3 modules (registry filled by a later import, config mutated after, compiled initial state, reset, substate) | A5-01 | **[re-validated]** p1 `[]`, p4 backend `rx.field(LATE)` `['late']`, p7 `{}`, p13 `Cfg('',0)`, p10/p11/p12 snapshot (0.9.12: p4 snapshot and p5 factory called once) |
| `probes/v1/probe_patchdict.py` (S) | `mock.patch.dict(MODULE_DEFAULTS)` of a module dict used as a default | A5-01 | **[re-validated]** patch ignored: `filters={'status': 'open'}` (0.9.12/a4: `closed`) |
| `probes/probe_lock_tree.py` (S) | defaults that cannot be deep-copied (Lock, Holder, open file, httpx client, Engine, module), ClassVar, `set_default(Holder())` | A5-02, A5-03 | **[re-validated]** backend and frontend non-copyable default: `TypeError: cannot pickle '_thread.lock' object` at the class statement, no var name; ClassVar OK; `set_default(default_factory=...)` OK |
| `probes/lockmod/run_lockmod.py fevar\|mystate` (S) | import of a module with a non-copyable frontend (`fevar`) / backend (`mystate`) default; prints exception, cause, notes | A5-02, A5-03 | **[re-validated]** both `IMPORT FAILED: TypeError: cannot pickle '_thread.lock' object`, notes None (0.9.12/a4 fevar: `VarTypeError ... Found var "...holder..."`) |
| `apps/lockapp` | `reflex compile` with `_lock: threading.Lock = threading.Lock()` | A5-03 | rc=1 at import, traceback ends at the user's `class CacheState` line (0.9.12: rc=1 inside compile_state; a4: compiles). Run: `cp -r $CS/apps/lockapp $W/run/ && cd $W/run/lockapp && $SB/envs/$NEW/bin/reflex compile` |
| `probes/probe_large.py <list\|ndarray\|df\|dictrows>`, `probes/probe_mem.py <rows\|floats\|ndarray> <keep\|drop>`, `probes/probe_time.py <rows\|floats\|ndarray\|df>`, `probes/probe_many_states.py` (S) | class-definition time and resident memory of 8-60 MB defaults; 400 small states | A5-04 | **[re-validated]** classdef +0.3-3 s, snapshot held while the module keeps its reference (+36.7 MB rows, +8.1 MB floats, +50 MB ndarray); 400 states ≈ 280 ms. Timings noisy on a shared host |
| `probes/probe_09_default_trap.py`, `probes/probe_09_trap2.py` (S) | the upgrade guide's "on 0.9 `.default = []` was safe" sentence | A5-05 | 0.10.0: `.default = NEW` shared by every instance (leaks); `set_default(['sd'])` isolates (`s4=['sd','x'] s5=['sd']`) **[re-validated]**. The 0.9 half needs a 0.9.12 venv (`CTRL`): frontend default shared + leaks, backend `.default` ignored |
| `probes/probe_owner_msg.py` (S) | which class the TypeError names (P, substate, grandchild, mixin, ComponentState, SharedState, framework vars) and whether following its suggestion works | #7519 owner naming | **[re-validated]** identical to a5: declaring state named ("…of P, inherited by C"); fix works; `C.router = None` accepted silently (pre-existing, `router` is a descriptor); mixin/template rows print "fix FAILED NoneType" (cannot instantiate, expected) |
| `apps/badassign5` | `Child.count = 5` at module level in a real app; `BADASSIGN_FIX=1` applies the suggested `set_default` | #7516/#7519 | `reflex run` rc=1 with the message at the user's line; with `BADASSIGN_FIX=1` the page shows `5/5`, `6/6` after bump. Run with `bin/start_app.sh $NEW <copy> 3302 8302 <log>` |
| `apps/lateapp` + `bin/drive_late.py <base> <out.json>` | e2e of A5-01: class-body list, `rx.field` list, decorator registry, lifespan config | A5-01 | 0.10.0 renders `|` / `red,green|` / `<empty>` / `<empty>` (0.9.12, a4: `red,green|` / `red,green|` / `plugin_a` / `api=https://x,retries=3`); no error or log line. Dev on 3302/8302 |
| `probes/probe_docs.py` (S) | every statement and sample of base_vars.md "Changing defaults", component_state.md, upgrading-to-0-10.md, the #7519 news entry | A5-05, docs | **[re-validated]** identical to a5 (only the random length in the numpy demo differs). Rows embed the 0.10.0 docs text: when the docs change, update the matching `row()` |
| `probes/docs_blocks.py <page.md>...` | version-independent: executes every ```python block of the given docs pages in page order and prints OK/EXC per block | docs drift | run on the PREV and NEW docs pages and diff; some blocks fail in isolation on every version (redefined substate, relative import, second `rx.App`) — only differences matter. **[validated: runs on 0.10.0 against the checkout docs]** |

### Class assignment / patching moot, field API (F-004, N-039, N-040, A3-01, A3-02, A3-04, N-005)
| path | exercises | findings | expected on 0.10.0 |
|---|---|---|---|
| `pytest/test_moot.py` (S) | 24 A3-01 patterns (`S.x = v`, setattr, `mock.patch.object`, `monkeypatch.setattr`, `patch.multiple`, del, substate, mixin) must raise the documented TypeError at the assignment line and leave the Field intact | F-004, N-039, A3-01 | **[re-validated]** 25 passed (fixed the file-name check after renaming; it now uses `Path(__file__).name`) |
| `pytest/test_converted.py` (S) | the same scenarios rewritten to `set_default` + field patching, monkeypatch/mock interplay | N-039, A3-01 | **[re-validated]** 25 passed |
| `pytest/test_converted_attr.py` (S) | the plain `Field.default` / `.default_factory` attribute API (still supported) | N-039 | **[re-validated]** 21 passed |
| `pytest/test_n039_fields.py` (S) | 17 var kinds × 6 field mechanisms round-trip; class spellings raise. `DOWNSTREAM=1` adds reflex-local-auth / google-auth / magic-link states (needs the `tp` venv) | N-039 | **[re-validated]** 204 passed, 1 skipped (a5 tp venv with DOWNSTREAM=1: 210 passed) |
| `pytest/test_undo_edge.py`, `pytest/test_v7_undo.py` (S) | original A3-01 leak repros (class assignment + undo stack) | A3-01 | **[re-validated]** collection ERROR: `TypeError ... Svc.__fields__['limit'].set_default(...)` at `Svc.limit = 10` — the expected "moot" outcome (a3 control: 4F/4P and 4F/16P) |
| `probes/probe_v8_storage.py` (S) | original A3-02: non-str defaults assigned to storage vars | A3-02, N-005 | **[re-validated]** every `St.x = ...` raises; script stops (rc=1) at its unguarded `St.opt = "y"` — expected |
| `probes/adv7495.py` (S) | 34 adversarial cases incl. 8-thread assign/restore stress | A3-04 | **[re-validated]** identical to a5: 12000 TypeErrors, final count 0 |
| `probes/probe_thread_setdefault.py`, `probes/probe_thread_fields.py` (S) | A3-04 adapted: 8 threads × 1500 `set_default`/field restore + concurrent instances | A3-04 | **[re-validated]** 0 errors, ends on declared defaults (count 0, `_f` 'd', items ['decl']); the `mock.patch.object(field, "default")` variant ends on a stale value exactly like a plain attribute (expected) |
| `probes/probe_storage_setdefault.py`, `probes/probe_storage_fields.py` (S) | storage defaults through `set_default` / `.default`: storage kept with name/options; plain str on a str-annotated var → ordinary var | N-005, A3-02 | **[re-validated]** identical to a5 |
| `probes/probe_internals.py`, `probes/probe_shared_default.py` (S) | ComponentState ×50 per-component defaults, mixins, ClassVar, setvar, SharedState, dynamic route, rx.Model list var; shared mutable `.default` | #7516 internals | **[re-validated]** identical to a5 (shared `.default` list leaks into new instances and reset, as documented) |
| `pytest/test_patch_substate.py` (S) | `mock.patch.object(Substate, inherited_var)` message (cleanup shows "deleting") | UX note | **[re-validated]** 2 failed / 2 passed: the two `test_show_*` fail on purpose to display the message |
| `pytest/test_min.py`, `pytest/test_monkeypatch_backend_var.py`, `pytest/test_monkeypatch_other_attrs.py` (S) | the a2-era downstream test-suite patterns (class-level monkeypatch / mock.patch of vars, computed vars, handlers, ClassVar) | F-004, N-039, N-040 | **[re-validated]** 1F/1P, 4F/2P, 1F/9P: every failure is the documented TypeError for patching a state var on the class (moot by design); non-var attributes patch fine |
| `pytest/downstream/test_pkg_states.py` | a user's test suite patching INSTALLED packages' states (local-auth LocalStorage, magic-link sync storage, google-auth, chat ComponentState, inherited var) + pristine checks | N-039 downstream | needs the `tp` venv; a3: 19/19. On 0.10.x the class-level patch tests are expected to fail with the TypeError (not re-run) |
| `probes/derive_a.py [venv]` (S, dev+prod) | F-001: class-level reads per declaration pattern (backend var → `Field`, ClassVar, mixin, ComponentState) | F-001 | **[re-validated]** completes rc 0; backend class reads return `Field` |
| `probes/derive_e_format.py [venv]` (S) | N-006: backend var used in the UI (f-string, format, concat, `id=`) | N-006 | **[re-validated]** `BackendVarFormatError` names `S._size.default_value()`; silent/other paths (`"x" + S._label` → `TypeError ... "Field"`, `inst.count = S._size` accepted) unchanged since a3 |

### add_var / auto setters / dev guard (A4-01, A4-02, N-008)
| path | exercises | findings | expected on 0.10.0 |
|---|---|---|---|
| `probes/probe_addvar.py` (S) | `P.add_var` then `C.add_var` on a substate, retry, `__init_subclass__` hook (D1), OrbitLab pattern (D2), guard (D3), class assignment of an inherited dynamic var (B1) | A4-01 | **[re-validated]** identical to a5: still TypeError ("'dyn' is a state var of P1, inherited by C2 …"), unbound field left, D1/D3 fail, B1 accepted (not fixed in 0.10.0) |
| `apps/dynhook` + `bin/drive_dynhook.py <url> <out.json> <shot.png>` | e2e of A4-01 (`Hooked.__init_subclass__` adds `loading` to every subclass) | A4-01 | 0.10.0: `reflex run` rc=1 at import (a3: independent vars; 0.9.12: aliased, wrong UI). Dev 3302/8302; prod single port with `DH_API_URL` |
| `probes/dynroute/probe_dynroute.py` (S) | dynamic route args never call add_var | A4-01 reach | **[re-validated]** 0 add_var calls, compile ok |
| `probes/probe_autoset2.py` from `probes/autoset_on` / `autoset_off` (S), `probes/autoset/probe_autoset.py` (S) | `state_auto_setters=True`: parent `set_color` + child `color` | A4-02 | **[re-validated]** on: TypeError at class definition naming the parent ("'set_color' is a state var of PColl, inherited by CColl"); off: classes created |
| `probes/guard7495.py`, `probes/guard_local_rename.py` (S, `REFLEX_ENV_MODE=dev\|prod`) | dev undefined-var guard for `_x__y` / mangled names (own, base, mixin, local, renamed) | N-008 | **[re-validated]** identical to a5: `_sneaky__name = 1` raises SetUndefinedStateVarError in dev, accepted in prod; legitimate mangled names accepted |

### Background tasks (N-024, A3-06)
| path | exercises | findings | expected on 0.10.0 |
|---|---|---|---|
| `apps/n024doc` + `bin/drive_n024.py BASE OUT_JSON SERVER_LOG` | the upgrade guide's Parent/Child sample: calling an inherited handler / writing an inherited var outside `async with self`, `type(self)` inside the lock | N-024, A3-06 | a3/a4 (code unchanged since): sample 1 raises ImmutableStateError, sample 2 works, direct inherited write outside the lock raises (0.9.12 wrote silently; with Redis it was lost). Documented since a4. Run: `bin/start_app.sh $NEW <copy> 3302 8302 <log>`; prod single port: `N024_API_URL=http://localhost:3301 ... 3301 3301 <log> --env prod` |

### State-store compatibility (N-004)
| path | exercises | findings | expected on 0.10.0 |
|---|---|---|---|
| `bin/n004_matrix.sh <outdir> <venv>...` (uses `probes/schema/`, `probes/disk/`, `probes/pickle_keys.py`, `probes/schema_hashes*.py`) | pickle save/load across versions at defaults 0/5, StateManagerDisk writer/reader/writer, schema hashes of several shapes | N-004 | **[re-validated 0.10.0 vs 0.10.0a5]** schema hash `bbd147dc…` both; HBase=2efae263… HChild=f2d2a961… HCfg=472cb6c5… HSd=cb3b6199… identical; pickles load both ways at d0/d5 (field values only, no dirty/_backend_vars keys); disk sessions continue both ways. 0.9.12 → 0.10 loads; 0.10 → 0.9.12 `StateSchemaMismatchError` / fresh (documented) |
| `bin/n004_redis_chain.sh [venv...]` + `bin/drive_resume.py` | prod + one Redis, apps/cse2e, one session token through PREV → NEW → PREV → NEW | N-004 | every phase arrives with the previous values (limit +1 per phase, items, mixin var), no server-log errors (a5: a4→a5→a4→a5) |
| `bin/fleet_phase.sh <venv> <label>` + `apps/fleet_app` + `bin/drive_fleet.py` | mixed fleet / rollback with a default change (`FLEET_DEFAULT`), one phase per call, prod on 3307 | N-004 | a3: forward kept, rollback to 0.9.12 fresh (nothing logged), default change kept. Recipe: start redis, `redis-cli -p 8309 flushall`, `MODE=new bin/fleet_phase.sh $PREV "1:prev"`, `bin/fleet_phase.sh $NEW "2:prev->new"`, `bin/fleet_phase.sh $PREV "3:rollback"`, `FLEET_DEFAULT=7 bin/fleet_phase.sh $NEW "4:d5->d7"`, then `bin/stop_app.sh $W/pids/fleet.pid` |

### E2E app, hot reload, AppHarness
| path | exercises | findings | expected on 0.10.0 |
|---|---|---|---|
| `apps/cse2e` + `bin/drive_cse2e.py <base> <out.json>` | `/` storage defaults via `set_default` (LocalStorage sync across tabs, Cookie options, SessionStorage, storage-annotated var under the default key, plain values not stored), `/cs` docs EditableText/ThemeToggle/ThemePick, `/post/[slug]`, `/misc` (field defaults, reset, computed, background task, get_state, mixin, ClassVar, client_state, SharedState, upload), `/late` | N-005, A3-02, F-004, A5-01 | **[re-validated dev]** 29/31: the 28 a4 checks + `/late` rx.field pass; the 2 `/late` class-body/registry checks FAIL by design (A5-01 snapshot). Console clean. a5: prod + Redis 9 workers same (only the favicon 404 in the console) |
| `bin/hot_reload.py <app_dir> <server_log> <base> <out.json>` | 7 edits of the running dev app's state file (add var + set_default, change set_default, rename, change class-body default, remove var, user `Svc.limit = 3`, fix) | dev reload | **[re-validated]** 6/6 value steps pass in 8-10 s; the user-error step logs the TypeError and the server keeps watching |
| `harness/test_harness.py` (+ `hshared_state.py`) | two AppHarness apps in one pytest process sharing a state module, each with its own `set_default` | AppHarness, reflex#7479 | a5: 2 passed (shared 10→11 / 20→21). Run: `cd harness && EXPECT_VENV=$NEW V_PREIMPORT=1 V_PORT_BASE=3305 V_OUT=$W/out/harness PYTHONPATH=$PWD $SB/envs/$NEW/bin/python -I -m pytest -s -p no:cacheprovider -p no:randomly test_harness.py` (`V_PREIMPORT=0` reproduces reflex#7479) |

### Downstream
| path | exercises | expected |
|---|---|---|
| `downstream/grep_downstream.sh [dir...]` | class-level writes (`Name.attr =`, `cls.attr =`, setattr, patch.object), `add_var`/`_create_setter` calls, and (via `grep_late.py`) state defaults bound to a module name the module later mutates, in `$SB/downloads/wheels/*.whl` (unpacked to `$W/downstream/unz`), enterprise wheel, auth packages, reflex-examples | a4/a5: enterprise writes only ClassVars; reflex-clerk 1.0.3 writes backend vars through the class (broken on every 0.10); dynoselect unreachable; no A5-01 pattern anywhere |
| `downstream/grep_late.py <dir>...` | AST heuristic for A5-01 | 0 hits in reflex-examples, enterprise, 37 wheels, auth packages |
| `downstream/packages.txt` | the 22 third-party packages (pinned) of the sweep; used by `build_venvs.sh ... tp` | |
| `probes/probe_dynoselect.py` | reflex-dynoselect `component.State._raw_options = options` | unreachable (create fails earlier on every version) |

## Validated on 0.10.0 (2026-10-09, venv `compact-class_state-rel` = reflex[db,testing]==0.10.0 + pydantic 2.14.0, py3.12)
- `py_compile` of every `.py` and `bash -n` of every `.sh`: clean.
- `bin/run_python_suite.sh` (from a copy of this directory): all probes match the a5 records line for line after
  normalizing versions/paths/timings (copydef, owner_msg, addvar, autoset on/off, dynroute, guard7495 + guard_local dev/prod,
  adv7495, storage_*, shared_default; docs differs only in the random numpy-demo length; internals/autoset differ only
  in a pydantic line number of a deprecation warning). pytest: moot 25 passed, converted 25, converted_attr 21,
  n039 204 + 1 skipped; undo_edge / v7 collection ERROR (expected); patch_substate 2F/2P (by design); test_min 1F/1P,
  backend_var 4F/2P, other_attrs 1F/9P (class patches raise, by design).
- Copy-at-definition: 0.10.0 snapshots exactly as a5 (as documented for 0.10.0). Owner message: identical to a5.
- N-004: `bin/n004_matrix.sh` 0.10.0 vs 0.10.0a5 (`a5_class_state-a5` venv): schema hash and every shape hash identical,
  pickles and disk sessions interchange in both directions.
- E2E `apps/cse2e` dev 3300/8300: 29/31 (2 by-design A5-01 fails), console clean; `bin/hot_reload.py` 6/6 + the expected
  TypeError step.
- Fixture fixes made: `test_moot.py` file-name check (rename), n024doc rxconfig no longer hardcodes ports 3474/8474,
  venv guards use `/envs/<name>/` (not `/scratchpad/envs/`), drivers take `DRIVER`/`CHROMIUM` from the environment.
- Not re-run on 0.10.0: prod + Redis cse2e, Redis/fleet chains, lateapp/badassign5/dynhook/n024doc/lockapp e2e,
  AppHarness, DOWNSTREAM=1 and test_pkg_states (tp venv), Python 3.11/3.14.

## Known-benign quirks
- `/late` checks in drive_cse2e and lateapp "fail" on 0.10.x: A5-01 is documented behaviour since 0.10.0.
- Prod console: `/favicon.ico` 404. Server logs: "Mutable default values are not recommended" (from `rx.field(LATE)`),
  `Expected field 'St.ann' to receive type LocalStorage` (#7499, storage-annotated var). `[ERROR] Unexpected exit from worker`
  only when `stop_app.sh` SIGTERMs the group.
- Instantiating a state in a bare thread raises `LookupError: RegistrationContext` on every version; thread probes use `contextvars.copy_context()`.
- `probe_owner_msg.py`: "fix FAILED NoneType" on mixin/template rows (cannot instantiate them).
- The disk-matrix client token must not contain `_` (the script maps it to `x`).

## Dropped (superseded or obsolete)
a4 `c4e2e`/`drive_c4e2e.py`, `test_a4_moot.py` (regex only), `test_harness_a4.py`, `probe_docs.py` (a4), `badassign`;
a5 `apps/c4e2e_a4src` (only needed to chain from a version without `set_default`); a3 `clse2e`, `e2e89`, `probe_v7_paths.py`,
`probe_v9_cs_keys.py`, `test_shared_state_harness.py`, `upgrade_pickle.py`, `redis_dump.py`, `addvar_probe.py`, py_orig/tpv runners;
a2 `derive_f_dunder.py` (aborts at a class assignment on 0.10; `guard7495.py` covers N-008), `derive_b*`/`derive_g_assign`/
`derive_i_storage_legacy`/`storage_assign_matrix` (class assignment, moot), `t1_*/t2_*` N-039/N-040 matrices (superseded by
`test_n039_fields.py` / `test_moot.py`), `e2e_classattr`, `core_a2`, `n005` app (covered by cse2e). All logs, out/, screenshots, freezes.
