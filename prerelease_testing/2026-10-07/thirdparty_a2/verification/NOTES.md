# Verification of T-1 and T-2 (cluster `thirdparty_a2`, reflex 0.10.0a2)

Independent adversarial verification of the explorer's two MEDIUM claims (`../NOTES.md` sections 5.1 and 5.2).
Python-level only: no server, redis or browser was started (so no ports were used and nothing needs killing).
The probes here were written **before** reading the explorer's probes; the explorer's own repros were then re-run
unmodified (section 6).

## 0. Verdicts

| claim | verdict | regression vs 0.10.0a1 | regression vs 0.9.12 | my severity (explorer: medium) |
|---|---|---|---|---|
| **T-1** class-level patch of a State var default cannot be undone (teardown `TypeError`, patched default leaks) | **CONFIRMED** (every var kind, `monkeypatch`, `mock.patch.object`, `pytest-mock`, manual restore; Python 3.11-3.14). Extended: leak scope, substate variant, doubles, sloppy annotations (section 4) | **yes** (a1 restores cleanly; but a1's patch semantics were the F-004 "descriptor replaced" bug that #7461 fixed) | **yes** (0.9.12: no error, no leak, but the patch never reached instances) | **medium, low prevalence**: loud and non-local (later tests fail), trivial workarounds, rare idiom |
| **T-2** class-level assignment to an unannotated placeholder raises, callables are called | **NARROWED**: every fact reproduces (179 of 255 assignments raise on a2 vs 0 on a1 and 0.9.12; user code ran in 42) but it is the documented, review-requested design of #7461, limited to unannotated or too-narrow slots, and no one of the 22 third-party packages hits it | **yes** for the assignment call | **yes** for the assignment call | **low** (edge case; `ClassVar` or an accepting annotation is the supported path) |

Cause verdict (T-1): the explorer's cause is **right but incomplete**. It is two independent defects that compound
(section 3): the in-place mutation of the single shared `Field` (the saved "old value" is the mutated object) and the
explicit rejection of `Field` values. Relaxing only the rejection would hide the error and keep the leak (experiment,
section 4.6).

## 1. Setup (PyPI only, isolated)

| venv (under `$SB/envs/`) | contents |
|---|---|
| `verify_tp_0-a2` | python 3.12.3, `reflex==0.10.0a2`, `reflex-base==0.10.0a2`, siblings at their a2 versions, pydantic 2.13.5, pytest 9.1.1, pytest-mock 3.16.0, greenlet 3.5.6 |
| `verify_tp_0-a2-py311`, `-py313`, `-py314` | same pins on Python 3.11.17 / 3.13.16 / 3.14.6 |
| `verify_tp_0-a1` | `reflex==0.10.0a1` + the a1 sibling versions, pydantic held at 2.13.5 (as in the other venvs), same pytest |
| `verify_tp_0-s0912` | `reflex==0.9.12`, same pytest |
| `thirdparty_a2-a2`, `thirdparty-alpha`, `thirdparty-stable` (shared, read-only, from the explorer) | the 22 third-party packages; used only for the clerk/dynoselect probes and the source scan |

Exact pins: `reqs/{a2,a1,s0912}.all.txt` (a `pip freeze` of the campaign venvs + pytest + pytest-mock).
Every probe starts with `assert f"/envs/{EXPECT_VENV}/" in reflex.__file__` and runs as `python -I` from
`$SB/apps/verify_tp_0/probes` (a neutral directory). Telemetry off.

## 2. Rerun commands

```bash
export SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
cp -r <this directory> $SB/apps/verify_tp_0_rerun        # the script refuses to run inside a checkout
cd $SB/apps/verify_tp_0_rerun && SB=$SB bash run_all.sh   # ~25 s; creates the three venvs from reqs/*.all.txt if missing
# outputs land in out_rerun/ (non-zero exit codes of some probes are EXPECTED: failing baselines / failing a2 tests)
```

Individual probes (all print per-version results; `EXPECT_VENV` names the venv directory):

```bash
cd $SB/apps/verify_tp_0_rerun/probes
for n in a2 a1 s0912; do
  REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=verify_tp_0-$n $SB/envs/verify_tp_0-$n/bin/python -I t1_matrix.py out.json   # 15 var kinds x 7 mechanisms
  REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=verify_tp_0-$n $SB/envs/verify_tp_0-$n/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_t1_pytest.py
done
# minimal repros (validated on all three versions)
python -I -m pytest -p no:cacheprovider -q test_min_t1.py     # T-1: a2 "1 failed, 1 passed, 1 error"; a1/0.9.12 "2 passed"
python -I min_t2.py                                           # T-2: a2 raises + user callable ran; a1/0.9.12 assign silently
```

Files: `probes/` (all scripts), `out/` (outputs per version; `*.json` are machine-readable), `explorer_repro_rerun/`
(the explorer's repro files executed unmodified on my venvs), `reqs/`.

## 3. What the published source says (reflex-base 0.10.0a2, `reflex_base/vars/base.py`, md5 `5c87bb47dce0...`)

| lines | fact |
|---|---|
| `4764-4817` | `BaseStateMeta.__setattr__`. `4780-4783`: if the name is a field declared by this class (or inherited unchanged) it is handled here, otherwise `type.__setattr__`. `4789`: `_accepts_default(declared, value)`. `4790-4797`: a value the annotation rejects that is `callable` is **called** (`default = value()`) to validate. `4803-4804`: accepted callable result -> `declared.default = MISSING; declared.default_factory = value`. `4815-4817`: `declared.default = ...; declared.default_factory = ...`. Both mutate the one `Field` object in place |
| `4676-4701` | `_accepts_default` (the explorer cites `4684-4703`, which starts inside the docstring and ends two lines after the function). `4689-4694`: a `Var` raises `A Var cannot be a field default...`; `4695-4700`: a `Field` raises `A Field cannot overwrite another field. Define a computed var to read the field at runtime instead.`; `4701`: `_isinstance(value, declared.outer_type_, nested=1, treat_var_as_type=False)` |
| `4310-4311` | `Field.__get__` with no instance returns `self` when the field has no `Var` (every backend var) and `self._var` otherwise (frontend vars). So `getattr(Cls, "_x")` is the `Field`, `getattr(Cls, "x")` is a `Var` |
| `4564-4598`, `4597` | `_unannotated_fields`: an unannotated class attribute becomes `Field._with_default(value, figure_out_type(value))`, so `_client = None` is typed `NoneType`, `_n = 0` `int`, `_s = ''` `str`, `_flag = False` `bool`, `_l = []` `Sequence[NoReturn]`, `_d = {}` `Mapping[NoReturn, NoReturn]` |
| `4659-4673` | `_default_arguments`: any non-immutable default (a live client, a lock, a list) becomes `default_factory=partial(copy.deepcopy, value)` |
| `4193-4195` | `Field.__set__` type-checks only non-backend vars ("Only values sent to the client are type checked"): instance writes to a backend var are unchecked, class writes are strictly checked |
| `4749-4895` | `BaseStateMeta` defines no `__delattr__` (`delattr` removes the descriptor from the class dict; `__fields__` keeps listing it) |

How the standard tools snapshot a class attribute (installed pytest 9.1.1, CPython 3.12 `unittest.mock`):
`_pytest/monkeypatch.py:240` `oldval = getattr(...)`, then `244-246` "avoid class descriptors": for a class target
`oldval = target.__dict__.get(name)`; `undo()` at `407-411` does `setattr(obj, name, oldval)`.
`unittest/mock.py:1421` `original = target.__dict__[name]`; `__exit__` `1583-1594` does `setattr(self.target, self.attribute, self.temp_original)`.
For a class both tools therefore save the raw class-dict entry, which for a State var is **the live `Field`**, and restore
by assigning it back. (It is not only monkeypatch: `getattr`-based manual restores also fail, with the `Field` for
backend vars and a `Var` for frontend vars.)

Design intent (PR #7461 "Preserve state descriptors when assigning class defaults", merged 2026-10-07 04:30Z by masenf;
read via the GitHub tools): the docs added in the PR (`docs/vars/base_vars.md` "Changing Defaults") say assigned defaults
"must match the field's declared type", "Var and Field assignments are rejected, including fresh `rx.field(...)` objects",
a zero-argument callable the annotation does not accept "is called once when assigned to validate its result", "Reading
`MyState._token` through the class returns its field descriptor", "an inherited var belongs to the state that declared
it", and recommend `ClassVar` for shared configuration. Review threads: the maintainer asked for the type check ("assigning
an invalid type as the default would break assumptions"), for calling a callable to validate it ("that way a function can
be assigned to a Field to update the default factory"), and removed `Field` replacement ("remove all of the machinery that
it required ... just reject Var and Field assignments"). The PR's tests assign and read back; none patches and restores.

## 4. T-1 results

### 4.1 Matrix: 15 var kinds x 7 mechanisms (`out/t1_matrix.*.txt|json`, summary `out/t1_mech_counts.txt`, per-cell table `out/t1_compare.txt`)

Kinds: private annotated, public annotated, `rx.field` public, `rx.field` private, unannotated private, unannotated public,
mutable default (`list[int] = [1]`), `rx.field(default_factory=...)`, annotation excluding the default (`_v: int = None`),
`Optional[int] = None`, mixin private, mixin public, substate (patch `Child`, declared on `Parent`), ComponentState
private, ComponentState public. Cell = (kinds with an undo/patch error) / (kinds whose default leaked) / (kinds where a
fresh instance sees the patch), of 15:

| mechanism | 0.10.0a2 | 0.10.0a1 | 0.9.12 |
|---|---|---|---|
| `monkeypatch.setattr(cls, name, v)` | **15/15/15** | 0/0/15 | 0/0/0 |
| `mock.patch.object(cls, name, v)` | **15/15/15** | 0/0/15 | 0/0/0 |
| manual: `old = cls.__dict__[n]; set; set(old)` | 15/14/14 (1 harness `KeyError`: inherited name not in `cls.__dict__`) | 1/0/14 | 3/0/0 |
| manual: `old = getattr(cls, n); set; set(old)` | **15/15/15** (`Field` for backend vars, `Var` for public vars) | 0/5/15 (public vars: the `Var` replaces the descriptor) | 0/0/0 |
| manual: re-assign the **original value** | **1/1/15** (only the `_v: int = None` kind) | 0/0/15 | 0/0/0 |
| `monkeypatch.setattr(<Field>, "default", v)` | 0/0/15 | 0/0/15 | 0/0/6 |
| `monkeypatch.delattr(cls, name)` | 1/0/0 (substate: inherited name, plain Python semantics) | 1/0/0 | 3/0/0 |

Reading it: a2 makes the patch visible (like a1) but never undoes it; a1 undoes it; 0.9.12 neither shows nor leaks it.
The same 30/30 monkeypatch+mock failures occur on Python 3.11, 3.12, 3.13 and 3.14 (`out/t1_matrix.a2-py3*.txt`).

### 4.2 Real pytest runner (`probes/test_t1_pytest.py`, `out/t1_pytest.*.txt`)

22 tests (patch test followed by a sentinel test per scenario, plus controls). a2: **`8 failed, 14 passed, 6 errors`**.
Teardown `ERROR` for `monkeypatch` on a private var, a public var, an `rx.field` var, a mixin var and `pytest-mock`
`mocker.patch.object` (all `TypeError: A Field cannot overwrite another field. Define a computed var to read the field at
runtime instead.`), and `AttributeError: type object 'Child' has no attribute '_plimit'` for a patch made through a
substate. The `with mock.patch.object(...)` block raises the same `TypeError` on exit (the test itself fails). Every
sentinel after a patch fails (`assert 99 == 5`, `'patched' == 'orig'`). a1: `22 passed`. 0.9.12: `9 failed, 13 passed`
(only because my patch tests assert the patch is visible; no teardown errors and every sentinel passes).

### 4.3 Controls (methods, handlers, computed vars, ClassVars) are fine

Matrix control group (`out/t1_matrix.a2.txt`, bottom) and `probes/test_t1_method_patterns.py` (5/5 pass on all three versions):
`mock.patch.object(State, "_actor", AsyncMock(return_value="A"))`, `patch.object(State, "_route_param", side_effect=...)`,
`monkeypatch.setattr(State, "_failed", lambda ...)`, `monkeypatch.setattr(State, "_mark_dirty", MagicMock(spec=State._mark_dirty))`
(patterns seen in public Reflex repos, section 7) all patch and restore cleanly; so do public methods, handlers, a computed var
replaced by a `property`, and a `ClassVar`. (Side fact: on 0.9.12 a patch of a public method is silently ignored by
instances, apparently because handlers resolve through the event-handler registry; a1 and a2 honour it.)
The explorer's `test_monkeypatch_other_attrs.py` **as written** shows 3 FAILED + 1 ERROR for its controls on a2; that is
collateral damage of its own leaking `count` test (`count` leaks as 41 into `doubled` and `bump`). With the var pair
deselected the 8 control tests pass (`explorer_repro_rerun/explorer_rerun.test_monkeypatch_other_attrs.a2.controls_only.txt`).

### 4.4 Is the problem only that monkeypatch stores the `Field` it read?

No, and re-assigning the original **value** does mostly restore cleanly: in 14 of 15 kinds `Svc._limit = 5` after the patch
returns to the original default (matrix row "re-assign the original value"). Two caveats: (1) when the annotation rejects
the original default, e.g. the very common `_v: int = None`, even that fails (`TypeError: Invalid default for field '_v':
expected <class 'int'>, got None`), so the only clean restore is patching the `Field` object's `default` attribute;
(2) for factory-backed defaults it restores an equivalent factory, not the identical one. The snapshot taken by the standard
tools is the raw class-dict entry (section 3), so any generic "save the class attribute, put it back" tool is affected, not
just pytest. `delattr` + restore is clean (no field is registered under the name while it is deleted).

### 4.5 Leak scope (`out/t1_blast_radius.a2.txt`)

The leaked default belongs to the **declaring** class: a mixin-using state and each ComponentState-generated state own their
copied `Field`, so patching one leaves the mixin, the sibling state and the ComponentState template untouched; but a var
declared on a parent is shared by the parent and every substate, so patching it through `ChildA` leaks into `Parent` and
`ChildB` (documented: "an inherited var belongs to the state that declared it"). Through a substate the monkeypatch
teardown cannot even try to restore: the saved old value is "absent from `Child.__dict__`", so it calls `delattr(Child, ...)`
and raises `AttributeError`.

### 4.6 Cause experiment (`probes/cause_experiment.py`, `out/cause_experiment.a2.txt`)

(a) `snap = Svc.__dict__["_limit"]` is the live `Field` and its `.default` flips from 5 to 99 when `Svc._limit = 99` runs
(aliasing). (b) Installing a hypothetical "assigning the declared `Field` back to itself is a no-op" wrapper over
`BaseStateMeta.__setattr__` in-process (no files touched) removes the teardown error but `field.default` stays 99 and new
instances read 99: **silent** pollution. So the mutation-in-place (4803-4804, 4815-4817) and the `Field` rejection
(4695-4700) are two causes; a fix that only relaxes the rejection makes the failure invisible.

### 4.7 The documented #7461 pattern still works (`probes/t1_documented.py`, `out/t1_documented.*.txt`)

On a2: `S.count = 10` and `S._token = "abc"` reach fresh instances; `S.count` is still a `Var` and renders in `rx.text`;
instances already initialised keep their values, never-initialised ones pick up the new default; `reset()` returns to the
last configured default; mutable defaults stay independent; a zero-argument callable is validated by exactly one call
and then called per instance; `Var` and `Field` assignments are rejected as documented; `ClassVar` assignment is ordinary;
ComponentState `cls.text = initial_value` in `get_component` gives per-component defaults (`one`, `two`, `default`), keeps
the UI bound to the var and `reset()` restores `one`. The only documented asymmetry is the round trip: the object read from
the class (`Field`) cannot be assigned back (rejected, as documented). a1 fails the same script on reset/mutable/callable/
ComponentState (that is F-004); 0.9.12 ignores all class assignments.

## 5. T-2 results

### 5.1 Matrix: 17 declarations x 15 assigned values = 255 assignments (`out/t2_matrix.*.txt|json`, `out/t2_summary.a2.txt`)

| | 0.10.0a2 | 0.10.0a1 | 0.9.12 |
|---|---|---|---|
| assignments that raise | **179** | 0 | 0 |
| assignments accepted | 76 | 255 | 255 |
| assignments during which user code ran | **42** | 0 | 0 |
| what a fresh instance then reads | the assigned value, or the result of the assigned callable | the assigned object (a function appears as a bound method) | the old default (assignment ignored) |

Identical totals on Python 3.11 / 3.13 / 3.14 (`out/t2_matrix.a2-py3*.txt`).

Which declarations trip it (value used for validation: the annotation, or for unannotated vars the type inferred from the default, base.py `4597`):

| declaration | validated against | accepts (from my 15 values) |
|---|---|---|
| `_c = None` (unannotated; public `c = None` identical) | `NoneType` | `None` only |
| `_n = 0` | `int` | ints |
| `_s = ''` | `str` | strs (and callables returning a str, as factories) |
| `_f = False` | `bool` | bools only (`1` is rejected) |
| `_l = []` / `_d = {}` | `Sequence[NoReturn]` / `Mapping[NoReturn, NoReturn]` | sequences / mappings |
| `_x: str = ''`, `_x: int = 0` | the annotation | strict |
| `_x: Optional[Client] = None`, `Client \| None`, `'Client \| None'` | the annotation | `Client`, `None`, spec'd mocks |
| `_x: Any = None`, `_x: object = None` | anything | everything (but see 5.3) |
| `_x: Callable[..., Any] \| None = None` | callables | any callable or `None` (stored as the value, not called) |
| `_x: Client = None` (annotation excludes the default) | `Client` | `Client`; **`None` itself is rejected** |
| `_x: httpx.Client \| None = None` | the annotation | `httpx.Client`, `None` (but see 5.3) |

### 5.2 Callables are called (documented behaviour) and so are test doubles

Counters (`out/t2_matrix.a2.txt`): assigning the class `Client`, a callable instance, or a zero-argument function to any
slot whose annotation rejects it runs that code once, then (if the result does not satisfy the annotation) raises. On a
`str` slot a function or callable instance is accepted as a **factory**: instances then read its result and it runs again
on each fresh instance. `probes/t2_mock_called.py` (`out/t2_mock_called.*.txt`): `setattr(Svc, "_client", MagicMock())` on
`Optional[Client]` or on an unannotated `None` slot raises **and the mock was called** (`called=True, call_count=1`);
`MagicMock(return_value=7)` on an `int` slot is kept as the factory and its `call_count` rises on every new instance; a
duck-typed `FakeClient()` double is rejected at patch time; `MagicMock(spec=Client)` is accepted and then its restore
fails as in T-1, leaving the mock as the class default (`probes/spec_mock_restore.py`: a2 raises, a1 and 0.9.12 restore cleanly). a1 and 0.9.12 never call or validate anything.

### 5.3 Extra finding: permissive slots accept an object that cannot be copied, the failure is deferred (`out/t2_deferred_deepcopy.*.txt`)

On a2, `Cfg._http = httpx.Client()` (slot `httpx.Client | None`) and `Cfg._lock = threading.Lock()` (slot `Any`) are
accepted, then the first read of the var on any new instance raises `TypeError: cannot pickle '_thread.RLock' object`
(`_default_arguments` stores `partial(copy.deepcopy, value)`). a1 returned the shared client, 0.9.12 ignored the assignment.
This follows the documented rule that defaults are copied per instance and are not shared; the error text does not mention
the class assignment. `ClassVar[httpx.Client | None]` works identically on all three versions (shared object, plain
class attribute, monkeypatch round trip clean: `out/t2_classvar_migration.*.txt`), so it is the correct migration.

### 5.4 Third-party source scan (22 packages, 156 `.py` files in `thirdparty_a2-a2`; `out/scan_thirdparty.txt` + regex cross-check)

Class-level assignment to State attributes after class creation exists in four packages:

| package | pattern | affected? |
|---|---|---|
| reflex-clerk 1.0.3 | `ClerkState._secret_key = props['secret_key']` (`clerk_provider.py:396`), `cls._secret_key / _jwt_public_keys / _clerk_api_client / _fetch_user = ...` (`124-168`); slots are annotated (`_secret_key: str = None`, `_clerk_api_client: ClerkAPIClient = None`, `_jwt_public_keys: List[Dict[str, str]] = []`, `_fetch_user: bool = True`) | **Not by T-2**: every value matches its annotation (`out/clerk_probe.*.txt`: class assignment reaches instances on a2, `set_fetch_user_on_auth(False)` now works, 0.9.12 ignored it). Broken on a2 by the **read** side (and on a1 until the first class assignment replaces the descriptor, the F-004 bug): `cls._secret_key is None` is `False` because the class read is a `Field`, so `ClerkState.secret_key` returns a `Field` (F-001/#7312, documented). A reset such as `ClerkState._secret_key = None` raises on a2 because the annotation is `str` |
| reflex-dynoselect 0.1.0 | `component.State._raw_options = options` (`dynoselect.py:443`) into `_raw_options: list[dict[str, str]] = []` | No: accepted (`Option` is a `dict` subclass); and now takes effect (0.9.12 instances read `[]`) (`out/dynoselect_slot_probe.*.txt`) |
| reflex-ag-grid 0.0.11 | `comp.State._grid_component = comp`, `comp.State._model_class = model_class` | No: both declared `ClassVar[...]` (ordinary assignment). The package does not import on any version (`reflex.base` is gone) |
| reflex-chat 0.0.2a1 | `cls.__fields__["messages"].default = ...`, `cls.process = fn` (undeclared name) | No: `Field.default` is a plain attribute, `process` is not a field (`out/tp_patterns_probe.*.txt`; the dynoselect/ag-grid parts of that probe fail for unrelated reasons and are inconclusive) |

The other 18 packages have no such assignment. The published first-party packages (`reflex`, `reflex-base`,
`reflex-components-*`; `out/scan_firstparty.txt`) assign only framework bookkeeping attributes (`cls.base_vars`,
`cls._settable_names`, ...), none of them declared fields. So: **no realistic third-party break of T-2 itself was found**.

## 6. Comparison with the explorer

* Re-ran unmodified on my venvs (`explorer_repro_rerun/`): `min/test_min.py` (a2 `1 failed, 1 passed, 1 error`; a1, 0.9.12 `2 passed`),
  `test_monkeypatch_backend_var.py` (a2 `5 failed, 1 passed, 1 error`; a1 `6 passed`; 0.9.12 `4 failed`, the patch not reaching
  instances), `test_monkeypatch_other_attrs.py`, `none_slot_probe.py`, `callable_assign_probe.py`, `mock_patch_probe.py`:
  all outputs match the explorer's table in section 5 of `../NOTES.md`. The written repro is sufficient to reproduce both issues.
* Corrections/additions: (1) `_accepts_default` is `4676-4701`, Field branch `4695-4700` (not `4684-4703`); `BaseStateMeta.__setattr__`
  `4764-4817` is right. (2) The explorer's "controls pass" claim is correct only in isolation (4.3). (3) The cause is two-part (4.6).
  (4) T-1 also leaks to the declaring parent and its other substates and fails with `AttributeError` through a substate (4.5).
  (5) Doubles: `MagicMock()` is *called* by the failed assignment, a callable double becomes the factory (5.2). (6) Deferred
  deepcopy failure (5.3). (7) The explorer's workaround "annotate the slot" is incomplete: an accepting annotation lets the
  assignment through but the per-instance deep copy replaces the shared object a1 provided; `ClassVar` is the faithful replacement.
* Not reproduced / refuted: nothing in the claims; the severity and realism are what I narrow.

## 7. Severity reasoning

**How common is monkeypatching State var defaults downstream?** Rare. Reflex's own tests patch methods and `ClassVar`s
(`tests/units/test_state.py:2994`, `BackgroundTaskState._started: ClassVar[asyncio.Event | None]`, patched with
`monkeypatch.setattr` at `:3119`; `get_delta`, `StateProxy.__aenter__`...). GitHub code search for patches of `State` classes in
Reflex repos (a few dozen hits looked at; keyword search, so only indicative) found private/async methods patched with `AsyncMock`
(reflex-dev/kern-mrp: `_actor`, `_closer`, `_principal`, `_route_param`, `_run`), `monkeypatch.setattr(State, "_mark_dirty", MagicMock(spec=...))`
(robert-koch-institut/mex-consent, reflex-dev/flexgen) and one suite (just-dna-lite) whose comment explains that patching a public
method through `monkeypatch` is silently ignored (they measured it) so it patches a private one instead; **no example of patching a declared var default**. On
0.9.12 such a patch never reached instances (only class-level reads saw it, and #7312 already changed those), so suites that "passed" there did not depend on it. Hence T-1 mostly hits people
who adopt the new #7461 feature and then test it, which is a small audience, but there the failure is a hard teardown error
whose advice ("define a computed var") is irrelevant, plus non-local failures in later tests. Medium on impact, low on prevalence;
cheap to fix or to document (use `ClassVar`, patch the instance, re-assign the original value, or patch `Field.default`).

**Is T-2 realistic?** An edge case. It needs an unannotated (the docs say vars "should provide type annotations") or too-narrow slot, a runtime class-level
assignment of a different type, and code that depended on it: on 0.9.12 instances ignored the assignment, on a1 it worked only through
the F-004 descriptor-replacement bug, and reading such a value back from the class is already broken by the documented #7312 change.
The calling of callables and the type check are the documented design. What deserves attention: the error text for an inferred type
(`expected <class 'NoneType'>`) names a type the user never wrote; mocks and callable objects are executed by an assignment; the deferred
deepcopy failure (5.3) is cryptic.

## 8. Not covered

No browser, server or `AppHarness` run (Python-level behaviours; a dev-mode e2e would not change either verdict). pydantic 2.14 prerelease
not re-tested (the var machinery does not use pydantic). Prevalence evidence is limited to GitHub keyword search, the 22 packages, and the
Reflex checkout's tests. Redis/multi-worker persistence of a leaked default was not exercised (defaults are not part of the schema).

## 9. Hints for a fix agent (NOT applied; nothing in the framework was changed)

* T-1 needs to address **both** causes (4.6). Replacing only the `Field` rejection (`base.py:4695-4700`) with an identity no-op turns the loud teardown error into silent
  cross-test pollution. Options: make `BaseStateMeta.__setattr__` copy-on-write (install a derived `Field` in the class dict and in `__fields__`/`__own_fields__` so previously saved
  `Field` objects stay pristine) and accept a `Field` that was this class's own earlier `Field` as a rebind; or keep the maintainer's "reject Field assignments" rule and instead
  document/provide a supported way to override a default temporarily (the working one today is `monkeypatch.setattr(State.get_fields()[name], "default", v)`; also `ClassVar`, or patching a
  state instance). Whatever is chosen, the current error text ("Define a computed var to read the field at runtime instead") is misleading for a restore; a mention of testing/`ClassVar`
  would help. `delattr` has no override (4.1) and is harmless.
* T-2 is documented behaviour; what could be improved is the message for an inferred type (`expected <class 'NoneType'>` for a var the user never annotated; suggest annotating or `ClassVar`),
  a note in the docs that an assigned callable, `Mock` or class is **called** (and that a callable on a `str` var becomes a per-instance factory), and the deferred
  `cannot pickle '_thread.RLock' object` when a live client is assigned to a permissive slot (5.3).
