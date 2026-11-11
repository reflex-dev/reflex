# Item `a5_class_state`: #7519 (`Field.set_default`, copy-at-definition, error owner) on reflex 0.10.0a5, plus re-runs of the class-state regressions

Status: **done** (about 75 min). Everything installs from PyPI. No python runs from the checkouts. Every probe asserts the
venv it imported reflex from (`EXPECT_VENV`). Published `reflex_base/vars/base.py` (md5 33d8a18c…) and `reflex/state.py`
(f5844c83…) in the a5 wheels are byte-identical to tag `v0.10.0a5`.

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a5_class_state     # work dir
export REFLEX_TELEMETRY_ENABLED=false
# rerun setup from the repo (never run python from the checkout):
D=/home/user/reflex/prerelease_testing/2026-10-08-a5/a5_class_state; A4=/home/user/reflex/prerelease_testing/2026-10-08-a4
mkdir -p $W/run && cp -r $D/{probes,bin,apps,harness,downstream,build_venvs.sh} $W/ && cp -r $A4/a4_class_state/orig $A4/a4_class_state/probes $W/run/ \
  && cp $D/probes_a4_converted/* $W/run/probes/ && mkdir -p $W/run/verify && cp -r $A4/verify_class_state/. $W/run/verify/ && mkdir -p $W/pids $W/logs $W/out
bash $W/build_venvs.sh && bash $W/build_venvs.sh tp
```
Ports: frontend 3300-3339 and backend 8300-8339, with redis on 8309. `bin/start_app.sh` refuses any other port.
Used: 3300/8300 (dev), 3301 (prod+Redis), 3302/8302 (lateapp), 3303 (badassign5, N-004 chain), and 3305/3306 + 8305/8306 (AppHarness).
One server ran at a time. All of them were killed, and nothing was left listening in my range.

## Venvs (`build_venvs.sh`; freezes in `logs/venv/`)
| venv | contents |
|---|---|
| `a5_class_state-a5` | py3.12, `reflex[db,testing]==0.10.0a5` `reflex-base==0.10.0a5` `pydantic<2.14` pytest pytest-mock pytest-asyncio numpy pandas playwright 1.63.0 |
| `a5_class_state-a4` / `-s912` | the same with `==0.10.0a4` / `==0.9.12` (+greenlet) |
| `a5_class_state-a5-py311` / `-a5-py314` | py3.11.17 / 3.14.6, `reflex[db]==0.10.0a5` + the same test deps |
| `a5_class_state-tp` | `bash build_venvs.sh tp`: a5 + the 22 third-party packages of the a3 sweep + authlib + pytest |

These shared venvs were used read-only: `a4_class_state-a3` (0.10.0a3, the positive control), `a4_class_state-tp` (a4 + 22 packages), `a5`, `a4`,
`stable`, `a5-ent` and `driver`. The `pandas` that `--prerelease=allow` resolved is 3.1.0rc0. It is only used by `probe_large.py df`.

## Part 1: #7519 regression hunt (a5 vs a4 vs 0.9.12)

### (a) Mutable class-body default populated AFTER the class statement: **REGRESSION vs a4 and 0.9.12 (silent, undocumented)**
`probes/probe_copydef.py` rows a1-a10 and e14, plus `probes/probe_copydef_extra.py` (add_var). Logs: `logs/p1/copydef.{s912,a4,a5,a5-py311,a5-py314}.txt`.
```bash
cd $W/probes && for v in s912 a4 a5; do EXPECT_VENV=a5_class_state-$v $SB/envs/a5_class_state-$v/bin/python -I probe_copydef.py; done
```
| pattern | 0.9.12 | a4 | a5 |
|---|---|---|---|
| a1 `options: list[str] = OPTIONS`, `OPTIONS.append("late")` after the class | new session `['late']` | `['late']` | **`[]`** |
| a2 backend `_handlers: dict = REG`, REG filled by a decorator after the class | `{'plugin_a': …}` | same | **`{}`** |
| a5 backend `_config: dict = CONFIG`, CONFIG updated later (lifespan / lazy load), new instance + `reset()` | loaded config | loaded config | **`{}`** |
| a8 `State.__fields__['options'].default_value()` at UI build | `['late']` | `['late']` | **`[]`** |
| a9 unannotated public list / a10 backend list filled in a loop | live | live | **snapshot** |
| a6 unannotated override of an inherited var in a substate | (BaseVarShadowsInheritedVarError) | live | **snapshot** |
| e14 ComponentState class default appended before `create()` | live | live | **snapshot** |
| `State.add_var("dyn", list, LATE)` then `LATE.append` | live | live | **snapshot** |
| a3 `rx.field(LATE)`, and a4 `rx.field(default_factory=lambda: LATE)` | live | live | **live** (inconsistent with the plain class-body form) |
| a7 tuple holding a list (`is_immutable(tuple)`, no copy) | shared + leaks | same | same (pre-existing) |

E2E (`apps/lateapp`, the same source on every version; `bin/drive_late.py`, dev 3302/8302; `out/e2e/late-*.json/png`). The page renders `LateState.options`
(the class-body list, extended after the class), `field_opts` (`rx.field` of the same list), the backend registry filled by `@register`, and the backend
config filled by a lifespan task:
- 0.9.12 and a4: `red,green|` / `red,green|` / `plugin_a` / `api=https://x,retries=3`
- **a5: `|` / `red,green|` / `<empty>` / `<empty>`**. There is no error, warning or log line. The c5e2e `/late` page in dev and in prod+Redis (9 workers) shows the same.

Docs and changelog: the snapshot is stated only in the PR body ("a mutable class-declared default is deep-copied once when its class is created").
The CHANGELOG entry (reflex-base 0.10.0a5 Features) and docs talk about `set_default` copying. Neither the upgrade guide nor `base_vars.md` says that a class-body default is now snapshotted.
Downstream: a heuristic AST grep (`downstream/grep_late.py`, `logs/p1/downstream_late_grep.txt`) of reflex-examples, the enterprise a5 wheel, 37
third-party wheels, local-auth, google-auth and magic-link found **no** state default bound to a module-level name that the module later mutates.
The 22-package import sweep on a5 is identical to a4 (`logs/p1/import_sweep.*`), and all 112 enterprise a5 modules import on a5 (`logs/p1/enterprise_import.a5.txt`).

### (b) Defaults that cannot be deep-copied (rows b1-b14; `probes/probe_lock_tree.py`; `logs/p1/lock_tree.txt`, `lock_traceback.txt`, `frontend_noncopyable_msg.txt`)
| default | 0.9.12 | a4 | a5 |
|---|---|---|---|
| backend `_lock: Any = threading.Lock()`, `_h = Holder()` (holds a Lock), `open(...)`, `httpx.AsyncClient()`, `threading.Event()`, a module object, a sqlalchemy Engine, unannotated `_lock = Lock()` | fails at **every root-state init**: every session is broken | fails only on **first access** of that var; the rest of the app works (root init OK) | fails at **class definition, so import fails** (`reflex run` exits) |
| frontend `h: Any = Holder()` / `h: Holder = Holder()` / unannotated `lock = Lock()` | class def: clear `VarTypeError: State vars must be of a serializable type … Found var "…holder…" with type <class 'Holder'>` | same clear VarTypeError | class def: **`TypeError: cannot pickle '_thread.lock' object`** from copy.py. The var name and the actionable message are lost |
| `rx.field(Holder())` (backend) | class def | first access | first access (rx.field is not copied up front) |
| `ClassVar[...] = Lock()` | shared, OK | OK | OK |
| `set_default(Holder())` | n/a (`.default = Holder()` copied per instance) | n/a (`.default` shared) | raises the same pickle TypeError at the call |
| `set_default(default_factory=lambda: H)` | n/a | n/a | OK, shared by identity |

The a5 backend error is `TypeError: cannot pickle '_thread.lock' object`. Its traceback runs from the user's `class X(rx.State):` line through
`_annotated_fields` → `_with_default` → `_default_arguments` (base.py:4706). It names neither the var nor the `ClassVar` fix, but it now points at the
class statement (a4 and 0.9.12 pointed at instance access or init with no user frame). Failing fast at import is arguably better than 0.9.12. It
is a change from a4, where the rest of the app kept working.

### (c) Large defaults (`probes/probe_large.py`, `logs/p1/large.txt`, one process per cell)
| 50-60 MB backend default | classdef a4 → a5 | extra RSS held after classdef a4 → a5 | peak RSS a4 → a5 |
|---|---|---|---|
| `list(range(1.6M))` | 297 → 719 ms | +22 → +35 MB | 112 → 124 MB |
| `np.zeros(6.5M)` | 291 → 366 ms | +17 → +67 MB | 101 → 151 MB |
| DataFrame 819200×8 | 281 → 674 ms | +10 → +60 MB | 191 → 241 MB |
| 200k dict rows | 281 → 1061 ms | +22 → +71 MB | 154 → 196 MB |

a5 does one extra full deep copy at import. It also holds a second resident copy (the snapshot) as long as the module keeps the original,
so each prod worker carries it. First-instance cost is unchanged. 400 states with 4 small mutable defaults each: a4 ≈ a5 (≈300 ms;
0.9.12 912 ms; `logs/p1/many_states.txt`). Creating a ComponentState 100× with a 200k-item list default: a4 101 ms, a5 97-131 ms (no extra copy per create).

### (d) Identity-shared defaults: no change
`_reg: Registry = REGISTRY`, `_mark = object()`: `instance._reg is REGISTRY` is False on 0.9.12, a4 and a5 (always a copy). A `ClassVar` keeps identity on all of them.

### (e) Shapes (rows e1-e13; also `probe_internals.py` and `probe_shared_default.py` from the a4 pass, `logs/p2/internals.*`)
`rx.field([...])`, `rx.field(default_factory=…)`, `rx.Field[list[str]]`, class-body list, dict of lists, a dataclass object, a pydantic model, a backend set
and a nested dict all behave identically on 0.9.12, a4 and a5: instances isolated, `default_value()` declared, `reset()` correct. (`rx.Base` no longer exists on any of these
versions.) `ComponentState.create` ×60 with per-component `set_default`: 60 distinct fields, template untouched, `reset()` gives the configured
default. a4 == a5; 0.9.12 leaks the last configuration into every instance. `probe_internals.py` a4 vs a5 differs only in the error message wording.
Schema hash: the a4 pass's `schema_hashes.py` HBase/HChild/HCfg a5 == a4 == a3 (`logs/n004/schema_hashes.txt`). `schema_hashes_sd.py`: the shape configured
with `set_default` on a5 has the same hash as the shape configured with `.default`/`.default_factory` on a4/a3 (`cb3b6199…`; `logs/p2/schema_hashes_sd.txt`).

### `Field.set_default` and the docs samples (`probes/probe_docs_a5.py`, `logs/p1/docs.*`, a5 on 3.11/3.12/3.14 identical)
I ran every sample in `base_vars.md` (WatchlistState with `set_default("MSFT")`, `set_default([...])`, `set_default(default_factory=time.time)`; the
`mock.patch.object(field, "default", …)` sample; the backend var and ClassVar samples; the BackendVarState numpy demo; both `rx.field` samples),
in `component_state.md` (EditableText ×3 and ThemeToggle, verbatim) and in `upgrading-to-0-10.md` (httpx ClassVar + `set_default(10)` + field patch). Each statement checked true on a5:
- A change applies to new instances, to `reset()` and to an existing instance whose var was never stored. A stored value stays.
- `set_default()` with neither argument, `default_factory=None`, a default plus a factory, or `None` plus a factory raises TypeError with a clear message. `set_default(None)` and `default=` as a keyword work.
- The factory is called per instance and again on reset.
- A mutable default is copied when set and per instance, so the caller's later mutation does not reach it.
- No annotation check is done.
- Storage: a storage value keeps name and options, a str-annotated var given a plain str becomes an ordinary var, and a storage-annotated var given a plain str uses the default key. `probe_storage_setdefault.py` output is identical to `.default` on a5, a4 and a3.
- An inherited var changes for every inheriting state. `C.__fields__['x']` is P's field, so `set_default` through C changes P too, consistent with the docs.
- ComponentState per-component defaults work, `cls.text = …` raises TypeError, and named, per-key and unnamed storage keys behave as documented.
- A ClassVar lock is shared.

One statement is **inaccurate (docs, low)**. `upgrading-to-0-10.md` says: "On 0.9, assigning `State.__fields__["items"].default = []` was safe, because each instance
got a copy of the default." `probes/probe_09_default_trap.py` (`logs/p1/default_trap_09.txt`) shows this is true on 0.9.12 for a **backend** var only.
A regular var's `.default = []` was shared on 0.9.12 too: `items` leaks between sessions and into the field default, both on direct instances and on root-state trees. The
0.10 half of the paragraph (it is shared; `set_default` copies) is true.

### Error message owner (`probes/probe_owner_msg.py`, `logs/p1/owner_msg.{a4,a5}.txt`; the "fix works" column applies the message literally)
On a5 the message names: P for `P.x`/`P._b`; **P** for the substate `C.x`, the grandchild `G.x` and `del C.x` ("…of P, inherited by C; assigning it on C … `P.__fields__['x'].set_default(...)`, which applies to every state that inherits it");
K for a redeclared `K.x` (#7312 independent var); Mix for `Mix.m`; UsesMix for `UsesMix.m`; **UsesMix** for `SubOfUsesMix.m`; Shared for a SharedState;
`ET_n1` for a ComponentState instance class; ET for the template; `ETSub_n2` for a ComponentState subclass instance.
Following the suggestion gives the assigned-through class the new default in every case. (The probe cannot instantiate mixin and template classes, so "fix FAILED NoneType" on those rows is expected.)
e2e: `apps/badassign5` (`Child.count = 5` at module level) makes `reflex run` exit with rc=1 and the new message at the user's line. `BADASSIGN_FIX=1`
(`Base.__fields__['count'].set_default(5)`, as suggested) starts, and the browser shows `5/5`, then `6/6` after bump (`logs/e2e/badassign5-*`).
`C.is_hydrated = True` names the framework root `State` ("…of State, inherited by C"); the suggestion would change the framework default for every state. That is acceptable.
`C.router = None` is accepted silently on a4 and a5: `router` is a `_RouterDescriptor`, not a field. This is pre-existing, outside #7519, and not investigated further.

## Part 2: the class-state regressions re-run on a5 (positive control first)
```bash
cd $W/run/orig/undo_edge && EXPECT_VENV=<v> $SB/envs/<v>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_undo_edge.py
cd $W/run/orig/v7 && … test_v7_undo.py ; cd $W/run/orig/v8 && … -I probe_v8_storage.py ; cd $W/run/adv-<v> && … -I adv7495.py
cd $W/run/probes && EXPECT_VENV=a5_class_state-a5 $SB/envs/a5_class_state-a5/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q -s test_a5_moot.py   # also test_a5_converted.py, test_a5_n039_fields.py
```
(`run/orig` and `run/probes` are copies of the a4 pass's `orig/` and `probes/`. The a5 variants are in `probes_a4_converted/`.)
| repro | a3 (control) | a4 | a5 | 0.9.12 |
|---|---|---|---|---|
| A3-01 `test_undo_edge.py` | 4 failed / 4 passed (as recorded) | collection ERROR (TypeError at `Svc.limit = 10`) | same ERROR, a5 wording `Svc.__fields__['limit'].set_default(...)` | 7 failed |
| A3-01 `test_v7_undo.py` | 4 failed / 16 passed | collection ERROR | same ERROR (a5 wording) | 19 failed |
| A3-02 `probe_v8_storage.py` | accepted, storage dropped | every `St.x = …` raises; storage map unchanged | identical to a4 apart from the wording | accepted, ignored |
| A3-04 `adv7495.py` (34 cases) | thread stress count=10589 (corrupt) | 12000 TypeErrors, final count 0 | **identical to a4** after normalizing the message (`logs/p2/adv7495.*`) | count 0 |
| `test_a5_moot.py` (24 a4 cases + mixin message checks; regex for the a5 wording incl. "inherited by") | — | (a4 copy: 24 passed; a3 23 failed) | **25 passed** on 3.11/3.12/3.14 | — |
| `test_a4_moot.py` unchanged on a5 | | | 7 failed: **message regex only** (expected wording change) | |
| `test_a5_converted.py` (config via `set_default`, + 3 interplay cases with monkeypatch/mock) | | | **25 passed** on 3.11/3.12/3.14 | |
| `test_a4_converted.py` (`.default`/`.default_factory` API) | 21 passed | 21 passed | **21 passed** (the old field API still works) | |
| N-039 `test_a5_n039_fields.py` (17 var kinds × 6 mechanisms incl. `set_default` and `set_default(default_factory=)`) | | (a4 copy: 170 passed) | **204 passed** on 3.11/3.12/3.14; `DOWNSTREAM=1` on `a5_class_state-tp`: **210 passed** | |
| A3-04 adapted: `probe_thread_fields.py` / `probe_thread_setdefault.py` (8 threads × 1500, concurrent instances) | | | 0 errors; ends on the declared defaults (count 0, `_f` 'd', items ['decl']) on 3.11/3.12/3.14; the mock.patch variant follows plain-attribute semantics like a4 | |

- **N-005**: the Python level matches a3/a4 (above). E2E `apps/c5e2e` (a copy of the a4 c4e2e with every `.default =`/`.default_factory =` replaced by `set_default`, plus `/late`),
  driver `bin/drive_c5e2e.py`. **Dev 3300/8300: 28/28** of the a4 checks, with no console messages. **Prod + Redis 8309 (9 workers) on 3301: 28/28**; the console shows only the
  benign favicon 404. Those checks cover: `k_sync` written and synced across tabs, cookie `k_ck_opt` Strict at ~3600 s, `k_ss` in sessionStorage, the storage-annotated var under the default key,
  `opt`/`plainstr` not stored, a new tab restores storage, EditableText/ThemeToggle/ThemePick per-component defaults (set_default) and storage keys,
  dynamic route, field-configured defaults, reset, a background task, get_state, mixin, SharedState, client_state and upload. The 2 extra `/late` checks "fail" by design: that is the
  snapshot finding. Server logs have no tracebacks (`logs/e2e/c5-a5-*.raw.log`).
- **N-008** (`run/orig/guard7495.py`, `guard_local_rename.py`, dev and prod; `logs/n008/`): a5 output is identical to a4. `_sneaky__name = 1` raises
  SetUndefinedStateVarError in dev and is accepted in prod; own, base, mixin and local mangled names are accepted.
- **N-004** (`bin/n004_matrix.sh logs/n004 a5_class_state-a5 a5_class_state-a4 a4_class_state-a3 a5_class_state-s912`): the schema hash is the same on a5, a4 and a3
  (`bbd147dc…`; HBase/HChild/HCfg identical). a5↔a4↔a3 pickles load in every direction at defaults 0 and 5. 0.9.12→a5 loads at the same default.
  a5→0.9.12 raises StateSchemaMismatchError (documented). StateManagerDisk: a5↔a4 and a5↔a3 keep and continue the session in both directions; 0.9.12→a5 is kept;
  a5→0.9.12 starts fresh (documented). Redis e2e (`bin/n004_redis_chain.sh`, prod on 3303, redis 8309, `logs/n004/redis_chain.txt`): one token runs through
  **a4 → a5 → a4 → a5**, and every phase arrives with the previous phase's values (limit 10→11→12→13→14, items, mixin var). The server logs have no errors.
- **A4-01** (`run/verify/probe_addvar.py`, `logs/a4xx/probe_addvar.*`): **still broken on a5, with a different message**. `P.add_var("dyn")` followed by
  `C.add_var("dyn")` still raises TypeError, still leaves an unbound field in `C.__fields__`, and a retry still raises NameError. The message now reads
  "'dyn' is a state var of P1, inherited by C2; assigning it on C2 … Set its default with P1.__fields__['dyn'].set_default(...), which applies to every
  state that inherits it". It is now accurate about the inheritance and its fix does change C's value, but only by changing P's default too. It still does not mention add_var.
  D1/D2/D3 (`__init_subclass__` hook, OrbitLab pattern, `if name not in S.__fields__` guard) still fail. The guard gap (`E.dyn = 5` accepted through a
  substate, B1) is unchanged. `probe_dynroute.py`: 0 add_var calls, a4 == a5.
- **A4-02** (`run/verify/probe_autoset2.py` with `autoset_on/off`): **unchanged apart from the wording**. With `state_auto_setters=True`, a parent `set_color` plus a child `color`
  still raise TypeError at class definition. The message now names the parent ("'set_color' is a state var of PColl, inherited by CColl; assigning it on
  CColl …"). It still says "assigning", still suggests `set_default`/ClassVar, and still does not mention auto setters. With the default config the classes are created on every version.
- **Dev hot reload** (`bin/hot_reload.py`, `out/e2e/hot_reload-a5.json`): 7 edits of the c5e2e state file while dev is up. The edits add a var with `set_default`, change
  `set_default(10→12)` and `set_default(["cfg"]→["cfg2"])`, rename a var, change a class-body default and drop the config, remove a var, add a user `Svc.limit = 3`, then fix it.
  Every step reloads in 6-9 s with the expected values. The user-error step logs the a5 TypeError and the server keeps watching. There are no console errors.
- **AppHarness** (`harness/test_harness_a5.py`, `.default` replaced by `set_default`; ports 3305/3306): **2 passed** (shared 10→11 / 20→21, one-box / two-box).

## Cleanup
Every `.web/`, `node_modules/` and `.states/` under `$W` and in my pytest tmp dir (`/tmp/pytest-of-root/pytest-210`) has been deleted. Both redis instances and every server are stopped.
