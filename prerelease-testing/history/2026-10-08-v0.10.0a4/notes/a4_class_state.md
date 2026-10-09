# Item `a4_class_state` — #7516 (state var class assignment raises) on reflex 0.10.0a4: A3-01/02/04 re-run, N-005/N-039/N-008/N-004 re-check, regression hunt

Status: **done** (~95 min). Everything installs from PyPI; nothing runs from the checkouts; every probe asserts the venv
it imported reflex from (`EXPECT_VENV`). Published `reflex_base/vars/base.py` (md5 7cbfc433…) and `reflex/state.py`
(91b25294…) in the a4 wheel are byte-identical to tag `v0.10.0a4`.

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a4_class_state          # work dir; this directory is a copy of it minus .web/run/raw logs/unpacked wheels
export REFLEX_TELEMETRY_ENABLED=false
```
Ports: frontend 3300-3319, backend 8300-8319, redis 8309 (`bin/start_app.sh` refuses anything else). Used: 3300/8300 (dev),
3301 (prod), 3302/8302 (badassign), 3303 (N-004 chain), 3305/8305 + 3306/8306 (AppHarness).

## Venvs (`build_venvs.sh`, freezes in `logs/venv/`)
| venv | contents |
|---|---|
| `a4_class_state-a4` | py3.12, `reflex[db,testing]==0.10.0a4` `reflex-base==0.10.0a4` `pydantic<2.14` pytest 9.1.1 pytest-mock 3.16.0 pytest-asyncio playwright 1.63.0 |
| `a4_class_state-a4-py311` / `-a4-py314` | py3.11.17 / 3.14.6, `reflex[db]==0.10.0a4` + same test deps |
| `a4_class_state-a3` | py3.12, same with `==0.10.0a3` (positive control) |
| `a4_class_state-s912` | py3.12, `reflex[db,testing]==0.9.12` + greenlet (baseline) |
| `a4_class_state-tp` | `bash build_venvs.sh tp`: a4 + the 22 third-party packages of the a3 sweep (`a3_events_tp/tp/packages.txt`) + authlib + numpy |
Read-only shared venvs used for baselines: `a3_events_tp-all` (a3 + 22 pkgs), `a3_events_tp-s912` (0.9.12 + 22 pkgs), `driver`.

## Part 1 — original repros (positive control on a3 first) — `orig/` holds the UNCHANGED copies
```bash
cd $W/orig/undo_edge && EXPECT_VENV=a4_class_state-<v> $SB/envs/a4_class_state-<v>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_undo_edge.py
cd $W/orig/v7 && EXPECT_VENV=a4_class_state-<v> $SB/envs/a4_class_state-<v>/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q -s test_v7_undo.py
cd $W/orig/v8 && EXPECT_VENV=a4_class_state-<v> $SB/envs/a4_class_state-<v>/bin/python -I probe_v8_storage.py
mkdir -p $W/run/adv && cp $W/orig/adv7495.py $W/run/adv/ && cd $W/run/adv && EXPECT_VENV=a4_class_state-<v> $SB/envs/a4_class_state-<v>/bin/python -I adv7495.py
```
| repro | a3 (control) | a4 | 0.9.12 | logs |
|---|---|---|---|---|
| A3-01 `test_undo_edge.py` | 4 failed / 4 passed (as recorded) | collection ERROR: `Svc.limit = 10` (line 23) → `TypeError: 'limit' is a state var of Svc; assigning it on the class would replace the var. Set its default with Svc.__fields__['limit'].default = ..., or declare class-level config as ClassVar.` | 7 failed (assignments ignored) | `logs/part1/undo_edge.*` |
| A3-01 `test_v7_undo.py` | 4 failed / 16 passed (as recorded) | collection ERROR at the first `cls.limit = 10` (same TypeError) | 19 failed | `logs/part1/v7.*` |
| A3-02 `probe_v8_storage.py` | every None/int assignment accepted, storage dropped (as recorded) | every `St.x = ...` raises the TypeError; storage map, defaults, `_is_client_storage` unchanged; script stops at its unguarded `St.opt = "y"` | accepted but ignored, storage kept | `logs/part1/v8.*` |
| A3-04 `adv7495.py thread_stress_assign_restore` | 0 errors, `count=21369` (want 0) — corrupted (as recorded) | 12000 TypeErrors (every assignment), final `count=0`, `_f='d'` default 'd' factory None | 0 errors, count 0 | `logs/part1/adv7495.*` (all 34 cases; also py311/py314) |

### Moot in the documented way (`probes/test_a4_moot.py`, 24 tests; a4 3.11/3.12/3.14: 24 passed; a3 23 failed; 0.9.12 22 failed)
```bash
cd $W/probes && EXPECT_VENV=a4_class_state-a4 $SB/envs/a4_class_state-a4/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q -s test_a4_moot.py
```
Each A3-01 pattern raises the exact documented TypeError (regex-checked: name, class, "assigning"/"deleting") at the assignment
statement (first traceback frame in the test file is the assignment line), and afterwards: the class attribute is the SAME
Field object as before, `default_value()` is the declared default, a fresh instance reads it, writes + pickle round trip,
`reset()` restores, `Svc.limit` is still a Var. Patterns: `S.x = v` (frontend/backend/mutable), `setattr`, `S.limit = S.limit`
(Var → raises), `S._quota = S._quota` (own Field → silent no-op, documented), `mock.patch.object(S, "limit", Other.y)` (raises;
cleanup assigns the saved Field back = no-op, `__context__` None), `mock.patch.object(S, "limit", 7)`, `mocker.patch.object(S,
"_quota", rx.field(5))`, `monkeypatch.setattr(S, "limit", 99)` (raises, nothing recorded, teardown clean), `mock.patch.multiple`,
`mock.patch("mod.S.limit")`, `new_callable`, substate assignment / `del` of an inherited var ("deleting" TypeError), mixin and
mixin-using state. `monkeypatch.delattr(S, "_quota")` removes the descriptor (documented: delete-then-set replaces on purpose);
during the test a fresh instance raises AttributeError, after teardown the var is intact.
UX note: `mock.patch.object(Substate, "inherited_var", v)` surfaces the cleanup's "**deleting** it on the class would replace
the var" TypeError (with the "assigning" one as `__context__`) — slightly confusing, still names the fix.

### Converted to the supported API (`probes/test_a4_converted.py`, 21 tests: a4 3.11/3.12/3.14 and a3 all pass; 0.9.12 12 fail)
Config at import via `S.__fields__[...]` (`.default` / `.default_factory`), then: monkeypatch / `mock.patch.object` / mocker on
the field, nested patches, A3-01(a) (a Var patched in as the field default is accepted during the window — "the field does not
check the value", documented — and restored), (c) code under test re-setting the field default inside a monkeypatch window →
teardown restores the configured 10 (plain-attribute semantics; the A3-01(c) leak is gone), (d) PR recipe
`monkeypatch.delattr(S,"_quota")` + `monkeypatch.setattr(S,"_quota",77,raising=False)`: instances read 77 (a plain class
attribute; instance writes are untracked, dirty_vars empty) and teardown restores the Field; default_factory patching; patching
`default` over a factory (wins while patched, MISSING again after); patching through a substate's `__fields__` (same Field object
as the declaring state); a storage var patched with a storage value keeps storage (new name), with a plain str drops it (documented),
restored after. No leaked default anywhere.

### A3-04 adapted (`probes/probe_thread_fields.py`; a4 3.11/3.12/3.14, a3)
8 threads × 1500 set + restore-to-declared on the FIELD (incl. the `_f` default/default_factory pair) + concurrent instance
creation: 0 errors, ends on the declared default (count 0, `_f` 'd', factory None). 8 threads using `mock.patch.object(field,
"default", v)` (save/restore per thread, non-LIFO) end on a stale value — exactly like the same code on a plain Python object
attribute (`(2')` row): plain attribute semantics, no reflex undo stack any more. (Threads run in `contextvars.copy_context()`:
instantiating a state in a bare thread raises `LookupError: RegistrationContext` on 0.9.12, a3 and a4 alike — pre-existing.)

## Re-checks under the new semantics
- **N-005** — `probes/probe_storage_fields.py` (`logs/part1/storage_fields.*`, a4 == a3 on 3.11/3.12/3.14): storage defaults set
  through the field with a storage VALUE keep storage + name + options (LocalStorage sync, Cookie max_age/same_site/path,
  SessionStorage); a str-annotated var given a plain str / None / int becomes an ordinary var (documented); a storage-annotated var
  given a plain value stays storage under the default key/options (documented); a storage-annotated var with default MISSING + a
  factory returning LocalStorage(name, sync) compiles with that name/sync (0.9.12: name lost) — CHANGELOG #7461 statement true.
  E2E `apps/c4e2e` `/` (dev 28/28, prod+Redis 9 workers 28/28): `k_sync` written + syncs across tabs, cookie `k_ck_opt` SameSite=Strict
  ~3600 s, `k_ss` in sessionStorage, storage-annotated `ann` stored under the default full-name key (not `k_ann`), A3-02-converted
  `opt` (None) and `plainstr` not stored, new tab restores storage vars and shows defaults for the ordinary ones.
- **N-039** — `probes/test_n039_fields.py`: 17 var kinds (int/str/float/bool/list/dict/Optional/`rx.Field`+`rx.field`/factory field/
  dataclass/LocalStorage/Cookie/SessionStorage/backend int+list/inherited/mixin) × 4 field mechanisms round-trip, and the 4 class
  spellings (assign/setattr/monkeypatch/mock) raise and leave the field intact: a4 3.11/3.12/3.14 170 passed. Downstream
  (`DOWNSTREAM=1`, venv `a4_class_state-tp`): reflex-local-auth `LocalAuthState.auth_token` (LocalStorage), `LoginState.error_message`,
  `RegistrationState.new_user_id`, google-auth `GoogleAuthState.token_response_json`/`refresh_token`, magic-link
  `MagicLinkAuthState.session_token` patched through their fields round-trip, compiled storage map unchanged, class assignment raises: 176 passed.
- **N-008** — `orig/guard7495.py`, `orig/guard_local_rename.py` (`logs/n008/`): a4 output identical to a3 in dev and prod:
  `_sneaky__name = 1` raises SetUndefinedStateVarError in dev; own/base/mixin/`_Under`/`__Dunder`/ComponentState/local mangled names accepted; prod accepts all.
- **N-004** — `bin/n004_matrix.sh logs/n004 a4_class_state-a4 a4_class_state-a3 a4_class_state-s912`: schema hash a4 == a3
  (`bbd147dc…`; my 3 shapes incl. a field-configured default identical too, `logs/n004/schema_hashes.txt`); a4-saved pickle loads on a3 and
  vice versa at default 0 and 5; 0.9.12 → a4 loads (same default), a4 → 0.9.12 `StateSchemaMismatchError` (documented); a4 pickles hold field
  values only. StateManagerDisk (`logs/n004/disk_matrix.txt`): a3↔a4 both directions keep and continue the session; 0.9.12→a4 kept;
  a4→0.9.12 starts fresh (documented). Redis e2e (`bin/n004_redis_chain.sh`, prod 3303, redis 8309, `logs/n004/redis_chain.txt`):
  one token through a3 → a4 → a3 → a4: every phase arrives with the previous phase's values (limit 2→3→4→5, items, mixin var), no log errors.

## Part 2 — #7516 regression hunt
### Python level (`probes/probe_internals.py`, `probes/autoset/probe_autoset.py`; `logs/part2_internals.*`, a4 == on 3.11/3.14)
```bash
cd $W/probes && EXPECT_VENV=a4_class_state-<v> $SB/envs/a4_class_state-<v>/bin/python -I probe_internals.py
cd $W/probes/autoset && EXPECT_VENV=a4_class_state-<v> $SB/envs/a4_class_state-<v>/bin/python -I probe_autoset.py   # rxconfig: state_auto_setters=True
```
- ComponentState `.create` ×50 with docs-style `cls.__fields__[...]` defaults, `default_factory` and a per-instance named
  LocalStorage: each instance owns its defaults, template field untouched, 51 distinct storage keys, `reset()` → configured default (a3 same; 0.9.12 leaks the last config into every instance).
- `cls.text = initial` in `get_component` (the a3 docs pattern) → TypeError at `create()` (documented breaking change; docs updated).
- mixin: changing `Mix.__fields__` default affects only states created afterwards (docs true); `Mix.m = 2` / `UsesMix.m = 2` raise.
- ClassVar / new names assignable (incl. a ClassVar redeclaring an inherited var on a substate); `del C.x` of an inherited var
  raises "deleting"; `del P._b; P._b = 99` on the declaring class replaces the var (plain attribute) — as the PR says.
- setvar + auto setters, `rx._x.client_state`, `rx.SharedState` subclass (field default honored, `Collab.count = 1` raises),
  dynamic route `/post/[slug]` (DynamicRouteVar bound via `_bind_attr`), `rx.Model` list var with default_factory + pickle + reset: OK.
- **`add_var` anomaly**: `P.add_var("dyn", ...)` then `C.add_var("dyn", ...)` on a substate (C created before) → a4 raises the #7516
  TypeError ("Set its default with C.__fields__['dyn'].default") instead of add_var's own NameError, after `add_field` already
  inserted an unbound field into `C.__fields__`. a3 and 0.9.12 accepted it (shadowing). Cause: `_update_substate_vars` updates
  `substate.vars` but not `substate.__fields__`, so add_var's `name in cls.__fields__` check misses the inherited dynamic var.
- **auto-setter collision**: with `state_auto_setters=True`, `class P: set_color: str` + `class C(P): color: str` → a4 TypeError at class
  definition ("'set_color' is a state var of C; assigning it on the class…"), raised from `_create_setter` (state.py:1400).
  a3 raised a different TypeError ("Invalid default for field 'set_color'… EventSpec"); 0.9.12 created C (setter replaced the inherited var).

### E2E app `apps/c4e2e` (Chromium/Playwright; driver `bin/drive_c4e2e.py`)
```bash
cp -r $W/apps/c4e2e $W/run/e2e/c4-dev && PIDTAG=dev $W/bin/start_app.sh a4_class_state-a4 $W/run/e2e/c4-dev 3300 8300 $W/logs/e2e/c4-a4-dev.raw.log --loglevel debug
$W/bin/wait_up.sh http://localhost:3300/ 400 $W/pids/dev.pid
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/bin/drive_c4e2e.py http://localhost:3300 $W/out/e2e/c4-a4-dev.json
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/bin/hot_reload.py $W/run/e2e/c4-dev $W/logs/e2e/c4-a4-dev.raw.log http://localhost:3300 $W/out/e2e/hot_reload-a4.json
$W/bin/stop_app.sh $W/pids/dev.pid
# prod + Redis (9 granian workers)
setsid redis-server --port 8309 --save '' --appendonly no &
cp -r $W/apps/c4e2e $W/run/e2e/c4-prod && C4_API_URL=http://localhost:3301 REFLEX_REDIS_URL=redis://localhost:8309 PIDTAG=prod $W/bin/start_app.sh a4_class_state-a4 $W/run/e2e/c4-prod 3301 3301 $W/logs/e2e/c4-a4-prod.raw.log --env prod --loglevel debug
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/bin/drive_c4e2e.py http://localhost:3301 $W/out/e2e/c4-a4-prod-redis.json
```
Pages: `/` storage (above), `/cs` docs EditableText ×3 (`initial_value` via `cls.__fields__`) + ThemeToggle key a/b (docs, as written)
+ ThemePick (per-key storage + per-component `default_factory`), `/post/[slug]`, `/misc` (field-configured defaults, computed var,
reset, background task, get_state, mixin handler, ClassVar config incl. `SvcChild.limit: ClassVar` over the inherited var,
`rx._x.client_state`, `rx.SharedState` link/inc, upload). Results: **dev 28/28, prod+Redis 28/28** (`out/e2e/*.json`, screenshots).
Console: nothing in dev; prod only the benign `/favicon.ico` 404. Server logs: no tracebacks; only the known #7499
`Expected field 'St.ann' to receive type LocalStorage` lines (storage-annotated var, same as a3). Import-time `St.sync = ...`,
`Svc.limit = ...`, `SvcChild.items = ...`, `Mix.mval = ...`, `Collab.count = ...` all raise the documented TypeError (shown on the page).

**Dev hot reload** (`bin/hot_reload.py`, `out/e2e/hot_reload-a4.json`): 7 successive edits of the state file while `reflex run` dev is up —
add var + field default, change a field-configured default (10→12), rename a var, change a class-body default + drop the field config,
remove a var, add a user `Svc.limit = 3` (→ worker traceback ending in the documented TypeError pointing at the user's line, server keeps
watching), fix it — every step reloads in ~8 s with the expected values in a fresh browser, no TypeError from the framework, no console errors.

**Import-time `State.count = 5`** (`apps/badassign`): `reflex run` dev and `--env prod` on a4 exit rc=1 before starting any server with a
clean traceback ending at the user's line + the actionable message (`logs/e2e/badassign-a4-*.trimmed.log`). 0.9.12 starts and serves (silently accepted).

**AppHarness** (`harness/test_harness_a4.py`, adapted from the a3 verifier's two-app test; shared state module pre-imported = reflex#7479 workaround):
```bash
cd $W/harness && EXPECT_VENV=a4_class_state-a4 V_PREIMPORT=1 V_PORT_BASE=3305 V_OUT=$W/out/harness PYTHONPATH=$W/harness $SB/envs/a4_class_state-a4/bin/python -I -m pytest -s -p no:cacheprovider -p no:randomly test_harness_a4.py
```
Two apps in one pytest process, each configuring the shared state's default via `__fields__` (10 / 20) + a ComponentState per-component
default: **2 passed** (shared 10→11 / 20→21, box "one-box"/"two-box", local handlers work).

### Downstream
- grep of 36 published wheels (`$SB/downloads/wheels`), the enterprise a5 wheel and the local-auth/google-auth/magic-link sources for
  `<State>.<var> =`, `cls.<var> =`, `comp.State.<var> =`, `setattr(cls…)`, `patch.object(` (`bin/grep_downstream.sh` → `logs/downstream/grep_class_writes.txt`):
  - reflex-enterprise 0.9.7a5: every class-level write (`cls._model_class`, `cls._primary_key`, `comp.State._grid_component`,
    `cls._has_registered_endpoints`, `cls._has_registered_handlers`) targets a `ClassVar` → unaffected. local-auth, google-auth, magic-link: none.
  - **reflex-clerk 1.0.3**: `ClerkState._secret_key: str = None` (+ `_jwt_public_keys`, `_clerk_api_client`, `_fetch_user`) are backend vars written
    through the class: `clerk_provider(secret_key="sk_test_123")` (its documented usage) now raises the #7516 TypeError at page build;
    `ClerkState.set_fetch_user_on_auth(...)` too. a3 accepted it but class reads return a `Field`, so the package was already broken on every 0.10
    alpha (its route also fails to build: `MISSING_EXPORT Event`); 0.9.12 works (`logs/downstream/clerk_probe.*`).
  - reflex-dynoselect 0.1.0 `component.State._raw_options = options` (backend var) — unreachable: the wheel ships no option archives
    and `create` already fails earlier on 0.9.12, a3 and a4 (`logs/downstream/dynoselect.*`). community reflex-ag-grid / reflex-chat: ClassVar / not a var.
- import sweep of the 22 packages on a4 == a3 (`logs/downstream/import_sweep.*`).

### Docs (`probes/probe_docs.py`, `logs/docs_probe.*`; plus the e2e `/cs` page runs component_state.md's samples as written)
base_vars.md WatchlistState sample, field `mock.patch.object` sample, "uses its default when one is set" (a factory is ignored while a
default is set), "does not check the value against the annotation", "a default is shared by every instance" (`probes/probe_shared_default.py`:
a mutable `.default` list is shared and mutations leak into new instances and `reset()` — true, as warned), inherited var default changes for
every inheriting state, backend `MyState._token` is a Field / assignment raises / `default_value()` fresh copy / `rx.foreach(...default_value())`,
ClassVar sample, BackendVarState numpy demo (venv `a4_class_state-tp`); component_state.md: per-component defaults, "Assigning `cls.text` itself
raises TypeError", named key shared / per-key name / unnamed key per component; upgrading-to-0-10.md sample (httpx ClassVar client, field default,
field patch) runs as written; "On 0.9, `State.count = 10` replaced the class attribute, but new instances still started at the declared default"
true on 0.9.12; CHANGELOG #7516 / #7461 (a4 wording) statements true. #7513 (background-task inherited-var text): docs-only in a4;
`reflex/istate/` and the background-task code are unchanged a3→a4 (diff stat), and the a3 pass verified the behaviour the text describes.

## Not covered
- ClassVar per-worker runtime divergence in prod (plain per-process class attributes; not re-run).
- #7513 background-task sample not re-run e2e on a4 (code unchanged since a3, where a3_upgrade/a3_events_tp ran it).
- Enterprise apps e2e with the a5 wheel (grep + code review only: all class writes are ClassVars).
