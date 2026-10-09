# verify_class_state — independent verification of two #7516 issues reported by `a4_class_state`

Agent `verify_class_state`, 2026-10-08. Packages under test: published reflex 0.10.0a4 + reflex-base 0.10.0a4.
Baselines: published 0.10.0a3 and 0.9.12. Only PyPI venvs were used. Nothing was installed from the checkout, and no
python ran with the checkout as its cwd.

## Setup / rerun

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_class_state4          # working copy; to rerun from the repo: cp -r <this dir> $W  (never run python from the checkout)
# venvs (prebuilt, read-only): $SB/envs/a4 (0.10.0a4), $SB/envs/a3 (0.10.0a3), $SB/envs/stable (0.9.12),
#   $SB/envs/a4_class_state-{a4,a3,s912} (same versions + pytest), $SB/envs/driver (playwright)

# Issue 1 (add_var on a substate), pure Python
cd $W && for v in a4 a3 stable; do EXPECT_VENV=$v REFLEX_TELEMETRY_ENABLED=false $SB/envs/$v/bin/python -I probe_addvar.py > logs/probe_addvar.$v.txt 2>&1; done
# Issue 1, dynamic route args never call add_var
cd $W/dynroute && for v in a4 a3 stable; do EXPECT_VENV=$v REFLEX_TELEMETRY_ENABLED=false $SB/envs/$v/bin/python -I probe_dynroute.py; done
# Issue 1, real app (apps/dynhook): a4 dev + prod (fail at import), a3 / 0.9.12 dev + Chromium driver
cp -r $W/apps/dynhook $W/run/dynhook-a4 && cd $W/run/dynhook-a4 && REFLEX_TELEMETRY_ENABLED=false $SB/envs/a4/bin/reflex run --frontend-port 3320 --backend-port 8320      # rc=1
cp -r $W/apps/dynhook $W/run/dynhook-a4p && cd $W/run/dynhook-a4p && DH_API_URL=http://localhost:3321 REFLEX_TELEMETRY_ENABLED=false $SB/envs/a4/bin/reflex run --env prod --frontend-port 3321 --backend-port 3321   # rc=1
cp -r $W/apps/dynhook $W/run/dynhook-a3 && cd $W/run/dynhook-a3 && REFLEX_TELEMETRY_ENABLED=false setsid $SB/envs/a3/bin/reflex run --frontend-port 3322 --backend-port 8322 > $W/logs/dynhook-a3-dev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python -I $W/drive_dynhook.py http://localhost:3322/ $W/out/dynhook-a3-dev.json $W/out/dynhook-a3-dev.png
#   (kill the process group, then do the same with $SB/envs/stable on 3324/8324 -> out/dynhook-s912-dev.*)
# Issue 2 (auto setters)
cd $W/autoset_on  && for v in a4 a3 stable; do EXPECT_VENV=$v REFLEX_TELEMETRY_ENABLED=false $SB/envs/$v/bin/python -I ../probe_autoset2.py; done   # rxconfig: state_auto_setters=True
cd $W/autoset_off && for v in a4 a3 stable; do EXPECT_VENV=$v REFLEX_TELEMETRY_ENABLED=false $SB/envs/$v/bin/python -I ../probe_autoset2.py; done   # default config (control)
# Original reporter's repros (re-run, both reproduce verbatim)
cd $SB/apps/a4_class_state/probes && EXPECT_VENV=a4_class_state-a4 $SB/envs/a4_class_state-a4/bin/python -I probe_internals.py   # row "add_var parent/child"
cd $SB/apps/a4_class_state/probes/autoset && EXPECT_VENV=a4_class_state-a4 $SB/envs/a4_class_state-a4/bin/python -I probe_autoset.py
# Cosmetic anomaly (mock.patch.object through a substate). The two test_show_* tests fail on purpose so pytest shows what a user sees.
cd $W/patchprobe && for v in a4_class_state-a4 a4_class_state-a3 a4_class_state-s912; do EXPECT_VENV=$v $SB/envs/$v/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -q -s --tb=short test_patch_substate.py; done
```
Ports used: 3320, 3321, 3322/8322, 3324/8324, one server at a time. All were killed afterwards, and nothing was left listening in 3320-3339 / 8320-8339.

## VERIFICATION

### Issue 1: `State.add_var` on a substate, for a name an ancestor already got via `add_var`

**Reproduced verbatim.** The reporter's `probe_internals.py` row and my `probe_addvar.py` row A3 both show it.
`P.add_var("dyn", int, 7); C.add_var("dyn", int, 9)` raises on a4:
`TypeError: 'dyn' is a state var of C2; assigning it on the class would replace the var. Set its default with C2.__fields__['dyn'].default = ..., or declare class-level config as ClassVar.`
The raise comes from `add_var` → `add_field` (`setattr(cls, name, new_field)`, base.py:4934) → `BaseStateMeta.__setattr__` (base.py:4776).
It happens whether C was defined before P.add_var (A3) or after it (A10).

**Root cause confirmed** (`logs/probe_addvar.a4.txt` A1/A4, and source):
- `add_field` writes only `cls.__fields__`, not `__own_fields__`.
- `_update_substate_vars` writes only `substate.vars`.

So a substate's `__fields__` never contains an ancestor's dynamic var, and `'dyn' in C.__fields__` is False on all three versions.
`add_var`'s `name in cls.__fields__` check therefore passes. `add_field` then inserts a new Field into `C.__fields__`, and the
guard sees `dyn` in `C.__fields__` and resolves the name through the MRO to P's Field, so it raises.
The PR body states the assumption this breaks: "`add_var`/`add_field` bind through the guard, because `add_var` rejects any name
already in `__fields__`". That holds for the declaring class but not for a substate that inherits a dynamic var.

**What a3 / 0.9.12 actually did, and whether "accepted and shadows" is correct:**

| | a3 (0.10.0a3) | 0.9.12 |
|---|---|---|
| `C.add_var("dyn")` | accepted | accepted |
| C's var | independent: `C.dyn` → C's own js path, `c.dyn`=9, `c.dyn=3` leaves `p.dyn`=7, C dirty only, in `dict()`/pickle/`compile_state`, `reset()` → 9 | **aliased and broken**: `C.dyn`/`C.vars` → C's own js path and C's key is in `dict()`/`compile_state`, but instance reads/writes go to the PARENT (`c.dyn=3` → `p.dyn=3`, P dirty, C's key never changes); `reset()` leaves `p.dyn` = 9 (C's default leaks into P, because C's reset writes through to the parent) |
| static equivalent `class K(P): a: int = 5` | allowed, independent var (CHANGELOG 0.10.0a1, #7312: "A substate may now declare a var … with the same name as an inherited var: it gets an independent one of its own") | `BaseVarShadowsInheritedVarError`; add_var bypassed that check |

E2E (`apps/dynhook`; Chromium driver `drive_dynhook.py`). `Hooked.__init_subclass__` calls `cls.add_var("loading", bool, False)`, so
`Page1(Hooked)` and `Detail(Page1)` each get their own `loading`. The page renders both values and has one toggle button per state.
- **a3 dev** (`out/dynhook-a3-dev.json`): initial `page1:off/detail:off`. Toggle detail → `page1:off/detail:on`. Toggle page1 → `page1:on/detail:on`.
  The two vars are independent: **correct**. The console shows only benign noise.
- **0.9.12 dev** (`out/dynhook-s912-dev.json`): toggle detail → `page1:on/detail:off`. The detail button flips the PARENT's text and the
  detail text never changes: **wrong UI, silently**.
- **a4 dev and prod** (`logs/dynhook-a4-dev.log`, `logs/dynhook-a4-prod.log`): `reflex run` exits with rc=1 before any server starts.
  The traceback runs from the user's `class Detail(Page1):` line through the user's `cls.add_var(...)` line into `add_var`, `add_field` and `__setattr__`, and ends in the TypeError above.

So "accepted and shadows" is correct on a3 and matches 0.10's documented semantics. On 0.9.12 it was accepted but broken.

**Is the unbound field left in `C.__fields__` observable?** (a4, A4–A9). Afterwards `C.__fields__['dyn']` is a new Field
(`_owner=None`, default 9) that is not P's. It is inert for the instance: `c.dyn` reads and writes P's value, `dict()`, pickle,
`compile_state` and `reset()` ignore it (it is not in `base_vars`, and its `_owner` is not C), and the schema hash covers `base_vars` only.
It is visible in three ways:
1. A retry `C.add_var("dyn")` raises the misleading `NameError: The variable 'dyn' already exist` (A8), even though C has no var of its own.
2. Following the error message (`C.__fields__['dyn'].default = 11`) changes nothing: `c.dyn` stays 7 (A9). On this path the
   message's advice is a no-op. It also never mentions add_var, and the user never assigned anything.
3. `C.get_fields()['dyn']` is a field that "knows" no owning state. The 0.10 CHANGELOG tells users to use `get_fields()` because its fields know their state.

This only matters if user code catches the TypeError. Otherwise the app does not import.

**Framework / downstream paths: none.**
- Framework: a4 `reflex` and every installed `reflex_*` package define `add_var` but never call it. Dynamic route args
  (`setup_dynamic_args`) install `DynamicRouteVar`s via `_bind_attr`, not `add_var`. `dynroute/probe_dynroute.py` spies on
  `add_var` while adding `/a/[slug]`, `/b/[slug]`, `/c/[slug]/[[...splat]]` (a substate defined after the arg was installed) and `/d/[id]`,
  then compiles: 0 `add_var` calls and compile OK on a4, a3 and 0.9.12.
- Enterprise a5 wheel and the 36 third-party wheels (`$SB/apps/a4_class_state/downstream/unz/`), plus reflex-local-auth, google-auth and
  magic-link sources: no `add_var`, `_create_setter` or `add_field` calls.
- Docs site: `PropDocsState.add_var(...)` on a single state with no substates. Not affected.

**Realistic trigger (public code, GitHub code search):** only 3 app repos call `State.add_var`.
- `iqss-research/debriefly`: `if "form_id" not in rx.State.__fields__: rx.State.add_var(...)`, on the root only. Not affected.
  The same guard on a substate after its parent got the var still raises (row D3), because the substate's `__fields__` lacks the inherited name.
- `JCorson/patch-sim`: a module-level loop on one state. Not affected.
- `OrbitLab-OSS/OrbitLab` `orbitlab/web/utilities.py`: `class OrbitLabState(CacheBuster, rx.State)`, where `CacheBuster.__init_subclass__`
  runs `for var in cls.computed_vars: cls.add_var(f"_cached_{var}", bool, default_value=False)`. It has several substates of OrbitLabState.
  Because `computed_vars` holds only a class's own computed vars, it is **not** hit today (row D2: a substate with its own computed var is fine on a4).
  It **is** hit (a4 TypeError, a3/0.9.12 OK) as soon as a substate redeclares an inherited computed var, which 0.10 documents as supported (#7312).
- The generic pattern is a base whose `__init_subclass__` adds the same dynamic var to every subclass. Any 3-level hierarchy trips it (row D1, the e2e app).

**Related, same root cause: the guard misses inherited dynamic vars** (row B1). It only checks `name in cls.__fields__`, so
`E.dyn = 5` / `F.dyn = 5` on a substate of P (defined before or after `P.add_var`) is **accepted** on a4. `E.dyn` becomes the plain int 5,
and `e.dyn` reads 5 instead of P's value. The same assignment for a static inherited var (`E.a = 5`) and on the declaring class
(`P2.dyn = 5`) raises. a3 and 0.9.12 accepted every class assignment, so this is not a regression. It is a gap in the new guard.

**Verdict: CONFIRMED (narrowed).** Severity **LOW**.
- Regression vs **a3: yes**. a3 gives the correct, documented independent var; a4 refuses with an unrelated message.
- Regression vs **0.9.12: no** by the campaign definition. 0.9.12 accepted the call but produced aliased, wrong UI, and a4 fails loudly at import.
- No framework, enterprise or third-party path reaches it. It needs user code calling `add_var` on a substate for a name an ancestor
  already added via `add_var`: a subclass hook on a 3+ level tree, or the OrbitLab hook plus a redeclared computed var.
- The fix point is the PR's false assumption above. Either `add_field` must not go through the guard for a name `add_var` already
  vetted (as `_bind_attr` does), or `add_var` must account for inherited dynamic names. The message should not recommend `__fields__[...]` here, because it is a no-op on this path.

### Issue 2: `state_auto_setters=True`, a parent var `set_<x>` and a child var `<x>`

**Reproduced verbatim.** The reporter's `probe_autoset.py` and my `probe_autoset2.py` (`logs/probe_autoset2.*.on.txt`) both give this on a4:
`TypeError: 'set_color' is a state var of CColl; assigning it on the class would replace the var. Set its default with CColl.__fields__['set_color'].default = ..., or declare class-level config as ClassVar.`
The frames are `_init_var` (state.py:1303) → `_create_setter` (state.py:1400 `setattr(cls, setter_name, handler)`) → base.py:4776, at class definition.
A grandparent `set_size` with a grandchild `size` fails the same way.
- a3: a different TypeError (`Invalid default for field 'set_color': expected str, got EventSpec`).
- 0.9.12: the class is created.

**Default and reachability.** `state_auto_setters: bool = False` on a4, a3 **and** 0.9.12 (`reflex_base/config.py:264`).
It is reachable only by opting in, through `rxconfig` or `REFLEX_STATE_AUTO_SETTERS=true`. Opting in prints
"state_auto_setters has been deprecated in version 0.9.0 … removed in 1.0" at config load. Control: with the default config (`*.off.txt`)
the same classes are created on all three versions. GitHub code search finds 17 repos with `state_auto_setters=True` (e.g. reflex-dev/learn, hjpr/nursereports).
I found no state var named `set_<x>` in any downstream wheel or the enterprise a5 wheel.

**What 0.9.12 really did** (`logs/probe_autoset2.stable.on.txt`): `CColl.set_color` became the child's EventHandler. Its setter works
(`c.color='blue'`), the parent var still works through `PColl`, and instance reads on the child still return the string. But the inherited
var is no longer usable through the child class: `rx.text(CColl.set_color)` raises `ChildrenTypeError … received child EventHandler`.
So 0.9.12 silently left a half-broken namespace; it did not "work".

**Consistency.** When the collision is in ONE class (`set_color: str` and `color: str` on the same state), every version silently
lets the var win and creates no `set_color` setter (row 2). An explicit `@rx.event def set_color` in the child over an inherited var is
accepted on all versions (row 3). Only the auto-generated setter over an inherited var raises on a4.

**Message.** It names the right var and class, and the traceback shows `_create_setter`. But it says "assigning it on the class" when the
user assigned nothing, recommends `__fields__[...].default` or ClassVar (neither applies), and mentions neither auto setters nor the
colliding var `color`. The useful fixes (rename either var, define an explicit handler, or turn off the deprecated auto setters) are not suggested.
It is misleading but not wrong: the failure is loud, at import, and points at the right class.

**Verdict: CONFIRMED, reclassified to LOW / message quality.**
- Regression vs **0.9.12: technically yes**. An app that imported on 0.9.12 fails to import, but 0.9.12's result was itself half-broken.
- Regression vs **a3: no**. a3 also refused.
- It is reachable only with the deprecated opt-in plus a var literally named `set_<x>` in an ancestor of a state declaring `<x>`. I found no realistic trigger.
- Suggestion: have `_create_setter` skip when the setter name is a var anywhere in `cls.__fields__` (the var wins, as in the one-class case), or raise a dedicated error that names the colliding var and auto setters.

### Cosmetic anomaly: `mock.patch.object(Substate, "inherited_var", v)`

**CONFIRMED** (`logs/patch_substate.a4_class_state-a4.txt`).
- The exception that propagates is `TypeError: 'limit' is a state var of Child; deleting it on the class would replace the var…`.
  It is raised by mock's cleanup (`mock.py:1588 delattr` → `BaseStateMeta.__delattr__`).
- Its `__context__` is the "assigning" TypeError raised at `mock.py:1567 setattr`.
- Patching the declaring class raises only "assigning", and its cleanup is a no-op.
- Afterwards the var is intact: `Child.limit` is Parent's Var, and a fresh instance reads 10.
- The decorator form behaves the same.

The user can still tell what to do. pytest prints the "assigning" error first, then "During handling of the above exception, another
exception occurred:", then the "deleting" error. The frame for the user's own `with mock.patch.object(...)` line is shown, and both
messages name the same fix (`Child.__fields__['limit'].default = ...`). That fix is valid: it is the same Field object as Parent's, as the docs say.
Only the word "deleting" is odd, since the user deleted nothing. a3 and 0.9.12 accept the patch, which is the intended #7516 breaking change.
**Benign, cosmetic.**
