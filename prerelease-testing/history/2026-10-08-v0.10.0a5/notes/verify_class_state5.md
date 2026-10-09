# verify_class_state5: independent verification of the `a5_class_state` findings on #7519 (copy-at-definition, `Field.set_default`)

Status: **done** (about 45 min). Every package came from PyPI. No python ran with a checkout as cwd. Every probe asserts which venv it imported reflex from (`EXPECT_VENV`).
Ports: only 3340/8340 (a5 dev) and 3341/8341 (0.9.12 dev), one server at a time. Both were killed, and `curl` returned `000` on all four ports afterwards.
Every `.web/` and `.states/` I created has been deleted.

## Rerun

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_class_state5; D=/home/user/reflex/prerelease_testing/2026-10-08-a5
mkdir -p $W && cp -r $D/verify_class_state5/. $W/ && cp -r $D/a5_class_state/{probes,apps,bin} $W/   # never run from the checkout
export REFLEX_TELEMETRY_ENABLED=false
# reporter's probes, rerun unchanged
cd $W/probes && for v in s912 a4 a5; do EXPECT_VENV=a5_class_state-$v $SB/envs/a5_class_state-$v/bin/python -I probe_copydef.py > $W/logs/copydef.$v.txt; done
cd $W/probes && for v in s912 a4 a5; do EXPECT_VENV=a5_class_state-$v $SB/envs/a5_class_state-$v/bin/python -I probe_copydef_extra.py; done
cd $W/probes && EXPECT_VENV=a5_class_state-s912 $SB/envs/a5_class_state-s912/bin/python -I probe_09_default_trap.py
# my probes (venvs: stable = 0.9.12, a4, a5; the a5_class_state-* venvs carry numpy/pandas for v3)
cd $W/v1 && for v in stable a4 a5; do EXPECT_VENV=$v $SB/envs/$v/bin/python -I probe_v1.py; done          # finding 1, real class statements, 3 modules
cd $W/v1 && for v in stable a4 a5; do EXPECT_VENV=$v $SB/envs/$v/bin/python -I probe_patchdict.py; done   # finding 1, test-suite variant
cd $W/v2 && for m in fevar mystate; do for v in stable a4 a5; do EXPECT_VENV=$v $SB/envs/$v/bin/python -I run_lockmod.py $m; done; done  # findings 2+3
for v in stable a4 a5; do mkdir -p $W/lockapp_$v && cp -r $W/apps/lockapp/. $W/lockapp_$v/ && (cd $W/lockapp_$v && $SB/envs/$v/bin/reflex compile); done  # finding 3, real CLI
cd $W/v3 && for k in rows floats ndarray; do for m in keep drop; do for v in s912 a4 a5; do EXPECT_VENV=a5_class_state-$v $SB/envs/a5_class_state-$v/bin/python -I probe_mem.py $k $m; done; done; done
cd $W/v3 && for k in rows floats ndarray df; do for v in s912 a4 a5; do EXPECT_VENV=a5_class_state-$v $SB/envs/a5_class_state-$v/bin/python -I probe_time.py $k; done; done
cd $W/v4 && for v in stable a4 a5; do EXPECT_VENV=$v $SB/envs/$v/bin/python -I probe_09_trap2.py; done  # finding 5
# e2e (the reporter's lateapp, unchanged): one server at a time
mkdir -p $W/e2e/lateapp_a5 && cp -r $W/apps/lateapp/. $W/e2e/lateapp_a5/ && cd $W/e2e/lateapp_a5 && setsid $SB/envs/a5/bin/reflex run --frontend-port 3340 --backend-port 8340 > $W/logs/e2e_late_a5.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/bin/drive_late.py http://localhost:3340 $W/e2e/late-a5.json
# kill -TERM -- -<pgid of the reflex process>; then the same on 3341/8341 with $SB/envs/stable
```

## Source and PR facts (read with `git show v0.10.0a4|v0.10.0a5:packages/reflex-base/src/reflex_base/vars/base.py`, and GitHub MCP for #7519)

- The only change in `_default_arguments` is `functools.partial(copy.deepcopy, value)` → `functools.partial(copy.deepcopy, copy.deepcopy(value))`.
  Four paths call it: `Field._with_default` (an annotated class-body value), `_annotated_fields` and `BaseStateMeta.__new__` (a new default for an inherited field, annotated or not),
  `Field.set_default`, and `State.add_var`. **`rx.field(value)` does not go through it.** It still builds `partial(copy.deepcopy, value)`
  (base.py ~4410), so `rx.field(LATE)` stays live. That is where the reported inconsistency comes from.
- **Was copy-at-definition an explicit, reviewed decision?** It was *stated*, but nobody reviewed it. The PR body says: "`_default_arguments` now copies a mutable value once up front.
  Instances read the default lazily, so without that copy, a caller who changed their list after `set_default` would change the default too. The same protection now
  applies to `State.add_var`, and a mutable class-declared default is deep-copied once when its class is created." The rationale given is about `set_default` only.
  None of the 7 review threads (cubic ×2, greptile, masenf ×2, FarhanAliRaza ×2) or the approving review discusses class-declared defaults. FarhanAliRaza's manual test covered
  "a change to the source list after `set_default`". No unit test covers the class-body snapshot. The new tests (`test_field_set_default`, ...) exercise `set_default` only.
- **Docs and changelog (a5):** neither mentions it. The reflex-base 0.10.0a5 entry says "A mutable `default` is copied when set and again for each instance". That sentence is about
  `set_default`. `base_vars.md` says "`set_default` copies a mutable `default` ... later changes to the value you passed do not reach the default", which is also `set_default` only.
  The root CHANGELOG a5 section covers only #7360. The upgrade guide has nothing on class-body defaults. The a5 `base_vars.md` does say "Do not change defaults in event handlers, lifespan
  tasks, or at any other time after the app has started running". That is about changing a field's default, not about mutating the source object, and it endorses changes made **before** the app runs.
- CodSpeed flagged a 7.35% regression on `test_hydration_metadata[200]` on the PR. I did not attribute it.

## VERIFICATION

### Finding 1: mutable class-body default populated after the class statement is snapshotted. **CONFIRMED, NARROWED on the 0.9.12 baseline.** Severity MEDIUM (silent), low reach.

Reporter rows reproduced exactly (`logs/copydef.{s912,a4,a5}.txt`, `logs/copydef_extra.txt`). On a5, a1 `[]`, a2 `{}`, a5 `{}`, a8 `[]`, a9/a10 `[]`, e14 `[]` and add_var `[]`.
On 0.9.12 and a4 they are live, and a3/a4 (`rx.field`) are live on all three.

My own probe (`v1/probe_v1.py`, which uses real `class` statements across 3 modules, `logs/v1.txt`):

| row | 0.9.12 | a4 | a5 |
|---|---|---|---|
| p1 `options: list[str] = OPTIONS`, `OPTIONS.extend(...)` after the class | `['red','green']` | same | **`[]`** |
| p2 the list is filled **before** the class (control) | `['e1','e2']` | same | same |
| p3 the module name is **rebound** after the class (`OPTIONS = [...]`, control) | `[]` | `[]` | `[]` (has never been live) |
| p4 **backend** `_bf = rx.field(LATE)`, appended after | **`[]` (snapshot at classdef!)** | `['late']` | `['late']` |
| p5 **backend** `_stamp = rx.field(default_factory=time.time)` | **called once at classdef: every session gets the same value** | per instance | per instance |
| p6 frontend `rx.field(LATE)` | live | live | live |
| p7 backend registry filled when a later module is imported (`@register`) | `{'plugin_a': ...}` | same | **`{}`** |
| p13 backend dataclass config, attributes set after the class | `Cfg('https://x', 3)` | same | **`Cfg('', 0)`** |
| p8 naive "global" list that handlers append to; a new session's default | `['alice']` | same | **`[]`** |
| p10 `compile_state(rx.State)`, the compiled initial state (first render / prerender) | `['red','green']` | same | **`[]`** |
| p11 `reset()`, p12 substate inheriting the var | live | live | **snapshot** |

Test-suite variant (`v1/probe_patchdict.py`, `logs/patchdict.txt`): `mock.patch.dict(DEFAULT_FILTERS, {...})` on the module dict used as a default gives
0.9.12 `{'status': 'closed'}`, a4 `closed`, **a5 `open`**. The patch is silently ignored. This matters because 0.10 already turned the other patch route
(`monkeypatch.setattr(State, "x", ...)`) into a TypeError.

E2E (reporter's `apps/lateapp` and `bin/drive_late.py`, unchanged, dev mode, Chromium; `e2e/late-*.json/png`):
0.9.12 on 3341 shows `red,green|`, `red,green|`, `plugin_a`, `api=https://x,retries=3`. **a5 on 3340 shows `|`, `red,green|`, `<empty>`, `<empty>`.** There are no console errors, and the server logs show
only the benign "Mutable default values are not recommended" warning (from the `rx.field(LATE)` line). Both match the reporter.

Narrowing and answers:
- **Is 0.9.12 really "live, copied per instance"?** It is for plain class-body defaults (frontend and backend) and for frontend `rx.field(value)`. It is **not** for **backend
  vars declared with `rx.field(...)`**. 0.9.12 calls `default_value()` in `__init_subclass__` to fill `cls.backend_vars`, so `_x = rx.field(LATE)` is snapshotted at class
  definition, and `_t = rx.field(default_factory=time.time)` is evaluated **once** and then shared by every session (p4/p5). So 0.9.12 already had per-kind inconsistency, inverted from a5's.
  a4 was the first release with uniform live semantics, and a5 makes the plain class-body form a snapshot while `rx.field` stays live.
- Only **in-place mutation of the exact object** after the class statement is affected. Rebinding the name never worked on any version (p3). Data loaded before the class is unaffected (p2).
- Comparator: pydantic 2.13.5 keeps the live semantics (`L=[]; class M(BaseModel): x: list = L; L.append(...)` gives `M().x == ['late']`, copied). a5 diverges from what Python users get from pydantic.
- Reach: the reporter's AST grep found no instances (reflex-examples, the enterprise a5 wheel, 37 third-party wheels). My GitHub `search_code` queries (`"rx.State" "REGISTRY"`, `"(rx.State):" "list = GLOBAL"`,
  `"rx.State" "dict = CACHE"`, `"rx.State" "= SHARED_"`, `"rx.State" "_plugins" "register"`, `"rx.State" "lifespan" "CONFIG.update"`) returned 0 relevant hits.
  Token search cannot express the pattern structurally, so this is weak evidence. In reflex-examples the only state default bound to a module constant is `body: str = DEFAULT_BODY`, which is immutable.
  The realistic exposures are plugin registries filled by decorators in later-imported modules, config dicts filled at startup, and **test suites patching a module default dict**. All of them are uncommon, and none of them produce an error.
- Verdict: a silent behavior change versus both 0.9.12 and a4, with no error or log line. It is undocumented in the changelog and docs, and it was mentioned in the PR body without review or test. Real-world reach is low.
  **Recommendation:** fix before 0.10.0 final, because the fix is cheap and it also removes findings 2, 3 (message) and 4 for the class-body path. Make the up-front copy apply only to the
  explicit-call APIs (`set_default`, `add_var`), and keep `partial(copy.deepcopy, value)` for class-declared defaults, as on a4, 0.9.12 and in pydantic. Thread a `snapshot: bool` through
  `_default_arguments`, or copy in `set_default`/`add_var` themselves. If the snapshot is kept on purpose, it needs a Breaking-Changes line plus an upgrade-guide note ("a mutable class-body
  default is copied when the class is created; populate it before the class statement, or use `rx.field(default_factory=lambda: X)` / `set_default` after populating it").
  On its own it is not a release blocker.

### Finding 2: frontend var whose default cannot be deep-copied gives an opaque `TypeError`. **CONFIRMED.** LOW, message-only regression vs a4 and 0.9.12.

`v2/run_lockmod.py fevar` (`logs/lockmod.txt`). On 0.9.12 and a4 the import fails with `VarTypeError: State vars must be of a serializable type ... Found var "...fe_state.holder_rx_state_" with type <class 'fevar.Holder'>`.
On a5 the import fails with `TypeError: cannot pickle '_thread.lock' object`. The last frame is `copy.py:151`, no var name appears anywhere (no cause, context or notes), and the only user frame is `fevar.py:11 class FeState(rx.State):`.
The cause is that the deepcopy runs in the metaclass (`__new__` → `_annotated_fields` → `_with_default` → `_default_arguments`) before the `__init_subclass__` serializability check.
Reach is narrow. Every version fails at the class statement, so this only changes the message, and only for a value that is both non-deep-copyable and non-serializable.
A value that can be copied but not serialized still gets the VarTypeError on a5. Fix: drop the class-body snapshot (finding 1), or catch the copy error and re-raise it naming
`Class.var`, saying that frontend vars must be serializable, and suggesting `ClassVar`.

### Finding 3: backend var whose default cannot be deep-copied fails at import. **RECLASSIFIED: not a regression vs 0.9.12. A behavior change vs a4 only. LOW (message).**

`v2/run_lockmod.py mystate` and the real CLI with `apps/lockapp` and `reflex compile` (`logs/lockapp_compile.*.log`):
- **0.9.12:** the import succeeds, but **`reflex compile` exits 1** with `TypeError: cannot pickle '_thread.lock' object`. The failure comes from `compile_state` → `State.__init__` → `default_value` → `deepcopy`, with
  no user frame and no var name. So the app cannot start on 0.9.12 at all: `reflex run` compiles the same way. (The reporter wrote "fails at every root-state init", which is correct, and its consequence is that no app was ever served.)
- **a4:** `reflex compile` reports success, and other vars work. Only accessing `_lock` raises.
- **a5:** `reflex compile` exits 1 at import. The traceback ends with the user frame `lockapp.py line 6 class CacheState(rx.State):`, then `_default_arguments` and `copy.py`. No var name.
No working 0.9.12 app can contain this pattern in a state reachable from `rx.State`, so nobody upgrading from 0.9.12 breaks. a5 fails earlier than 0.9.12 and points at the user's class, which is better.
Only a4 tolerated it. The remaining problem is that the message names neither the var nor the documented `ClassVar` fix (the a5 `base_vars.md` already tells users to declare locks and clients as `ClassVar`).
Suggested fix: re-raise as `TypeError("default of CacheState._lock cannot be copied for each session; declare it ClassVar[...]")`.
If the class-body snapshot is reverted for finding 1, a5 goes back to a4's lazy failure. Keeping fail-fast would then need either an eager trial copy (which costs the finding 4 time) or acceptance of a4's behavior.

### Finding 4: large mutable defaults are copied once more at import and kept resident. **CONFIRMED, NARROWED.** LOW. Regression vs a4. Not a memory regression vs 0.9.12 once there is a session.

`v3/probe_mem.py` (tracemalloc, warm process: a throwaway state class is defined first so the framework's first-subclass cost is excluded; `logs/mem.txt`) and `v3/probe_time.py` (no tracemalloc, 3 runs, `logs/time.txt`;
load average was about 3 on 4 CPUs from other agents, so the times are noisy, but the order of magnitude is clear):

| default (backend `_data: Any`) | classdef time 0.9.12 / a4 / **a5** | held after classdef, **module keeps its reference** | same, **module drops it** | first instance 0.9.12 / a4 / a5 |
|---|---|---|---|---|
| 200k dict rows (37 MB) | ~1 / ~0.3 / **885-1125 ms** | 0 / 0 / **+36.7 MB** | 0 / 0 / 0 (peak +54 MB) | +73 / +37 / +37 MB |
| 1M floats (8 MB) | ~1 / ~0.3 / **264-278 ms** | 0 / 0 / **+8.1 MB** | 0 / 0 / 0 | +16 / +8 / +8 MB |
| ndarray 50 MiB (pages touched) | ~1 / ~0.2 / **224-385 ms** | 0 / 0 / **+50 MB** | 0 / 0 / 0 | +100 / +50 / +50 MB |
| DataFrame 50 MiB | ~1 / ~0.3 / 23-262 ms | | | |

- Is the snapshot held for the process lifetime? Yes. On a5, `Big.__fields__['_data'].default_factory.args[0]` is a separate object (`class holds the user's object itself=False`), owned by
  the class's Field, and state classes are never freed. On 0.9.12 and a4 the class holds the user's object itself (`True`), so there is no extra copy.
- The extra resident copy exists **only while the user's module keeps its own reference** (the usual `DATA = load(); class S: _data = DATA`). With an inline literal, or `del`, the snapshot
  replaces the original and the steady state equals a4. Only the transient peak remains.
- Reporter correction: the reporter's "+50 MB" ndarray/DataFrame rows used `np.zeros`, whose calloc pages are not resident until touched, so RSS overstated a4's baseline gap.
  The "after del" RSS rows are distorted by pymalloc arena retention. tracemalloc gives the clean numbers above.
- Per prod worker: +1 × the default's size, plus +0.3-1.1 s of import per 40-60 MB default, in each worker process. Prod with Redis runs `2*cpu+1` workers (`reflex/utils/processes.get_num_workers`),
  so on a 4-CPU host a 50 MB default kept in a module global costs about +450 MB in total. Dev hot reload pays the import time on every reload.
- Versus 0.9.12: 0.9.12 copies a backend default **twice** per instance (the Field `default_value()` into the instance attribute, plus the `_backend_vars` deepcopy), so its first-instance cost is 2×.
  With the in-memory manager and ≥1 session, a5 (data + snapshot + 1 per session) uses ≤ 0.9.12 (data + 2 per session). With Redis, where states are transient, a5's per-worker baseline is +1× vs 0.9.12.
- The pattern is documented ("a backend-only var is used to store a large data structure which is then paged to the frontend", base_vars.md), so it is realistic. Fix: same as finding 1, no up-front copy for class-declared defaults.

### Finding 5: upgrade-guide sentence about `.default = []` on 0.9. **CONFIRMED, REFINED.** LOW (docs).

Exact text (`git show v0.10.0a5:docs/changelog/upgrading/upgrading-to-0-10.md`, section "Assigning a state var through its class", paragraph after the code block):
> "On 0.9, assigning `State.__fields__["items"].default = []` was safe, because each instance got a copy of the default. In 0.10 every instance shares the field's `default`, so a mutable value assigned there leaks changes between sessions. `set_default(default=[])` copies a mutable value for each instance."

Two other details in that paragraph are slightly off. It uses `set_default(default=[])`, while the docs elsewhere use the positional `set_default([...])`; both work. It also mentions only `[]`.

What is true on 0.9.12 (`v4/probe_09_trap2.py`, `logs/default_trap2.txt`; reporter's `probe_09_default_trap.py` reproduced in `logs/default_trap_09.s912.txt`), with session trees built from `rx.State`:
- **Frontend var** `items: list[str] = ["decl"]`, then `.default = NEW`: new sessions get **the same object** (`a.items is b.items` → True). One session's `append` leaks into every other session and into `NEW` itself.
  `reset()` restores **`['decl']`**, the declared value, because the old `default_factory` stays set and 0.9.12's `reset()` prefers the factory. So on 0.9 this was neither safe nor consistent.
- **Backend var** `_bitems: list[str] = ["decl"]`, then `.default = NEW`: **ignored entirely**. New sessions still get `['decl']`, and `_bcount` `.default = 10` also stays `0`, because 0.9.12 captures backend defaults in
  `cls.backend_vars` at class definition. The reporter's "safe only for backend vars" is therefore vacuous: nothing was applied, so nothing could be shared.
- Frontend `count: int` `.default = 10` is applied (10), and `reset()` keeps 10.
- a4 and a5: frontend and backend `.default = NEW` are both applied and both shared (leaks), and `reset()` keeps the shared object. `set_default(['sd'])` isolates sessions (`s4=['sd','x']`, `s5=['sd']`). The 0.10 half of the paragraph is accurate.
Suggested wording: "On 0.9, assigning a mutable `.default` already shared it between sessions for regular vars (and `reset()` restored the declared default), and it had no effect on backend vars. In 0.10 it applies to both and is shared by every instance; use `set_default([...])`, which copies a mutable value for each instance."

## Artifacts
`v1/` (finding 1 probes plus `pkg/`), `v2/run_lockmod.py` with `lockmod/` (findings 2 and 3), `apps/lockapp/` (finding 3 CLI), `v3/` (finding 4), `v4/` (finding 5), `logs/`, `e2e/late-{a5,stable}.{json,png}`.
The reporter's probes, `apps/lateapp` and `bin/drive_late.py` were used unchanged from `../a5_class_state/`.
