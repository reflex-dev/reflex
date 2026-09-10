# Cluster `hybrid_property` — reflex 0.9.11a1 pre-release testing (2026-09-10)

Scope: PR #6812 (hybrid_property overhaul: setters, var functions as class/staticmethod or
under their own name, `None` var fn, inheritance/annotation fixes, backend var defaults from
a base `field()`, no descriptor resolution during class construction), PR #7014 (dataclass
metadata on MutableProxy classes), PR #6929 (attribute probes no longer trigger ForwardRef
resolution / no NameError under PEP 649 on 3.14). Everything below was run against the
PyPI packages only (`reflex==0.9.11a1`, baselines against `reflex==0.9.10.post2`), never
against the checkout.

Public import path verified: `from reflex.experimental import hybrid_property`
(also `rx._x.hybrid_property`). `reflex.vars` does NOT export it (same in 0.9.10.post2);
`reflex_base.vars.hybrid_property` is the module, `reflex_base.vars.hybrid_property.hybrid_property`
the class.

## Layout of this directory

| path | what |
| --- | --- |
| `hp_app/` | the test app (5 pages + a 3.14-only page). `rxconfig.py`, `hp_app/*.py` |
| `hp_app/hp_app/core_state.py` | `/` getter, setter (`self.full_name = ...` in a handler), deleter, var fn as `@classmethod`, `@staticmethod`, under its own name, var fn returning `None`, plain `@property` setter |
| `hp_app/hp_app/inherit_state.py` | `/inherit` plain base + reflex mixin hybrid properties, state annotating the same names, backend vars `_cache`/`_level` with defaults from the base `rx.field()`, substate, sibling attaching its own var fn via `HybridBase.label.var` |
| `hp_app/hp_app/combo_state.py` | `/combo` computed var depending on hybrid props, `@rx.memo` props bound to them, `rx._x.client_state`, background task using the setter via `async with self`, `rx.ComponentState` x2 with a hybrid setter |
| `hp_app/hp_app/dc_state.py` | `/dc` #7014 dataclass / frozen dataclass / nested list mutations through the proxy; `is_dataclass`, `__dataclass_params__`, `__match_args__`, `match`, `fields`, `asdict`, `astuple`, `replace` |
| `hp_app/hp_app/fwd_state.py` | `/fwd` `from __future__ import annotations`, later-defined forward ref (`Item.tag: Tag`), TYPE_CHECKING-only annotation (`Weighted.weight`) |
| `hp_app/hp_app/fwd_lazy_state.py` | `/lazy` (only registered on Python >= 3.14) PEP 649 lazy annotations, same shapes |
| `scripts/drive_hp.py` | Playwright driver: all pages, all interactions, console/pageerror/network capture (103 checks, 105 incl. `/lazy`) |
| `scripts/probe_*.py` | server-free probes run against both venvs (see below) |
| `scripts/typecheck/*.py` | pyright `reveal_type` probes |
| `scripts/find_404.py` | pins the prod console 404 to `/favicon.ico` |
| `logs/` | server logs (dev/prod/py3.14), driver reports (`drive_*.json/.txt`), probe outputs per venv, pyright outputs |
| `shots/{dev_smoke,prod_smoke,dev_py314}/` | full-page screenshots per page |

## Rerun commands

```
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad   # any scratch dir works
# venvs used: $SB/envs/smoke (0.9.11a1, py3.11), $SB/envs/base0910 (0.9.10.post2), $SB/envs/driver (playwright)
# own venvs:  uv venv $SB/envs/hp311 --python 3.11 && uv pip install --python $SB/envs/hp311/bin/python --prerelease=allow 'reflex==0.9.11a1' pyright
#             uv venv $SB/envs/hp314 --python 3.14 && uv pip install --python $SB/envs/hp314/bin/python --prerelease=allow 'reflex==0.9.11a1'
#             uv venv $SB/envs/hp_pyright_old --python 3.11 && uv pip install --python $SB/envs/hp_pyright_old/bin/python 'pyright==1.1.389'

cd hp_app
# dev (py3.11):  REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run --loglevel debug --frontend-port 3140 --backend-port 8140
# prod:          REFLEX_TELEMETRY_ENABLED=false $SB/envs/smoke/bin/reflex run --env prod --loglevel debug --frontend-port 3141 --backend-port 3141
# dev (py3.14):  REFLEX_TELEMETRY_ENABLED=false $SB/envs/hp314/bin/reflex run --loglevel debug --frontend-port 3142 --backend-port 8142
cd ..
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_hp.py http://localhost:3140 shots/dev_smoke logs/drive_dev_smoke.json --skip-lazy
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_hp.py http://localhost:3141 shots/prod_smoke logs/drive_prod_smoke.json --skip-lazy
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_hp.py http://localhost:3142 shots/dev_py314 logs/drive_dev_py314.json   # includes /lazy

# server-free probes (cwd must be hp_app so the app package is importable; never the checkout)
cd hp_app
for v in smoke base0910; do $SB/envs/$v/bin/python ../scripts/probe_6812_baseline.py; done
for v in smoke base0910; do $SB/envs/$v/bin/python ../scripts/probe_none_var.py; done
for v in smoke base0910; do $SB/envs/$v/bin/python ../scripts/probe_dataclass_proxy.py; done
for v in smoke base0910; do $SB/envs/$v/bin/python ../scripts/probe_edges.py; done
for v in smoke base0910 hp314; do PYTHONPATH=$PWD $SB/envs/$v/bin/python ../scripts/probe_fwd_mock.py; done
for v in smoke base0910; do $SB/envs/$v/bin/python ../scripts/probe_later_forward_ref.py; done

# pyright (node from /opt/node22)
cd ../scripts/typecheck
PATH=/opt/node22/bin:$PATH $SB/envs/hp311/bin/pyright --pythonpath $SB/envs/hp311/bin/python hp_types.py hp_types_isolate.py hp_types_anyfree.py      # pyright 1.1.413
PATH=/opt/node22/bin:$PATH $SB/envs/hp_pyright_old/bin/pyright --pythonpath $SB/envs/hp311/bin/python hp_types_isolate.py hp_types_anyfree.py       # pyright 1.1.389
PATH=/opt/node22/bin:$PATH $SB/envs/hp311/bin/pyright --pythonpath $SB/envs/base0910/bin/python hp_types.py hp_types_isolate.py                       # vs 0.9.10.post2
```

## Results summary

End-to-end (Chromium via Playwright): **dev 103/103, prod 103/103, Python 3.14 dev 105/105**
checks passed; zero page errors, zero failed requests, zero 4xx/5xx except the benign
`/favicon.ico` 404 in prod (app ships no favicon); no non-benign console warnings/errors;
server logs clean of tracebacks (the one traceback in `logs/dev_smoke.log`,
`AttributeError: 'dict' object has no attribute 'split'`, is from an earlier version of my
own test that passed `on_key_down`'s key-info dict to the setter — not a framework issue).
`logs/dev_py314.log` contains no `Failed to resolve ForwardRefs` and no `NameError`.

### #6812 — hybrid_property (all confirmed working in the browser)
- plain getter in `rx.text` (`full_name`), `rx.cond` (`has_last`, via classmethod var fn), `rx.foreach` (`upper_tags`, via `@staticmethod` var fn receiving the owner).
- var fn under its own name (`_scaled_var`): frontend shows x3, backend getter x2 -> both code paths distinguishable; the alias name is removed from the class.
- setter runs from an event handler (`self.full_name = value`) and from the frontend input (`on_blur`); frontend updates because the setter touches real vars (delta contains only `first`/`last`, never the property).
- deleter (`del self.full_name`) runs; cond flips.
- assignment to a hybrid property **without** setter -> `AttributeError: Hybrid property 'scaled' has no setter` (clear).
- plain `@property` with setter assigned in a handler works (0.9.10.post2: `SetUndefinedStateVarError`).
- var fn returning `None`: class access is `None`; backend getter still works (`secret_len_backend`).
- inheritance: plain base class + `rx.State, mixin=True` mixin hybrid properties survive `label: str` / `shout: str` annotations on the state; backend vars annotated on the state (`_cache: dict[str,int]`, `_level: int`) take the base `rx.field(default_factory=...)` / `rx.field(default=7)` defaults; substate reuses them; `HybridBase.label.var` on a sibling state attaches a var fn without mutating the base descriptor (`SiblingState.label` -> `name + "?"`, `InheritState.label` unchanged); inherited setter works.
- a raising `default_factory` surfaces at **class creation (import time)** with the original `ValueError` (0.9.10.post2 swallowed it and used `None`).
- combo: computed var `summary` depends on hybrid properties -> dependency tracking follows the getters (`first`, `last`, `n` changes all recompute); `@rx.memo` props bound to hybrid vars update; `rx._x.client_state` mixed into the same text; background task sets and reads the property through `StateProxy` inside `async with self`; two `rx.ComponentState` instances with a hybrid setter stay independent.
- var fn ran 0 times during class creation, once on first class access (0.9.10.post2: ran during class creation).
- 0.9.10.post2 baselines (`logs/probe_6812_base0910.txt`): setter assignment -> `SetUndefinedStateVarError`; annotated inherited name became storage (`doubled` = 0, listed in `get_fields()`); underscore-named inherited hybrid property annotated on the state -> instantiation fails `AttributeError: property '_foo' of 'GuardState' object has no setter`; base `field()` defaults -> `None`; factory error swallowed; `@classmethod` var fn -> `TypeError: 'classmethod' object is not callable` at class creation. All fixed in 0.9.11a1.

### #7014 — dataclass proxies (`/dc`, `logs/probe_dataclass_proxy_*.txt`)
`type(proxy).__dataclass_params__.frozen/eq` and `type(proxy).__match_args__` work for
plain, frozen and nested dataclasses (`PointMutableProxy`, `FrozenMutableProxy`,
`ShapeMutableProxy`); `is_dataclass` on instance and class; `fields`, `asdict` (incl. nested
list of dataclasses), `astuple`, `replace` (assigned back to state), positional `match`
patterns, nested mutations (`self.shape.points[0].x += 1`, `.append`, `self.shapes[0].points[1].y += 5`)
all reflected in the UI; frozen dataclass stays frozen (`FrozenInstanceError`).
0.9.10.post2: `type(val).__dataclass_params__` and `type(val).__match_args__` raise
`AttributeError: type object 'PointMutableProxy' has no attribute ...` (regression fixed).

### #6929 — ForwardRef probes (`logs/probe_fwd_mock_*.txt`)
`inspect.iscoroutinefunction(FwdState.weighted)` (ObjectVar over a dataclass with a
TYPE_CHECKING-only annotation) and `mock.patch.object(FwdState, "weighted"|"items"|"add"|"async_add")`
work on 3.11 and 3.14 without warnings in 0.9.11a1. 0.9.10.post2 logs
`Failed to resolve ForwardRefs for <class 'Weighted'>._is_coroutine due to name 'Unresolvable' is not defined`
four times for the single `iscoroutinefunction` call. On 3.14 with PEP 649 lazy annotations
(`fwd_lazy_state.py`) nothing raises `NameError`; `/lazy` page renders and updates.

## Issues / anomalies

### A. (medium) Class-level typing claim depends on pyright version; `Any` with current pyright 1.1.413
Changelog (reflex-base 0.9.11a1): "type checkers now resolve class-level access to the
frontend var's type ... without a var function it follows the var equivalent of the
getter's return type".
- pyright **1.1.413** (current latest; the repo pins `pyright` unpinned): `reveal_type(State.full)` (getter `-> str`) is `Any`; same for `int`, `bool`, `float`, `list[str]`, `dict[str,int]`, `int | None` getters and for a var fn under its own name. Only explicitly typed var functions resolve (`-> rx.Var[str]` => `Var[str]`, `-> None` => `None`). Instance access is correct (`str`, `int`). `logs/pyright_hp_types.txt`, `logs/pyright_isolate_hp311.txt`.
- pyright **1.1.389**: the same file reveals `StringVar[str]`, `NumberVar[int]`, `BooleanVar`, `ArrayVar[list[str]]`. `logs/pyright_1.1.389_hp311.txt`.
- Root cause (confirmed by `scripts/typecheck/hp_types_anyfree.py`, `logs/pyright_anyfree_hp311.txt`): the third type parameter defaults to `_V = Var[Any] | None`. With `Any` inside the `self` argument type, several `__get__` overloads match (`_STR`, `_STR | None`, `_SEQUENCE` since `str` is a `Sequence`, and the catch-all `-> _V`), and newer pyright applies the typing-spec rule "argument contains Any + multiple matching overloads with different return types => Any". An explicitly annotated `HybridProperty[str, S, Var[str] | None]` resolves to `StringVar[str]` even on 1.1.413.
- Not a regression: 0.9.10.post2 typed `State.full` as `HybridProperty` and produced false errors (`Cannot access attribute "upper" for class "HybridProperty"`, `Cannot assign to attribute "full"`), `logs/pyright_hp_types_base0910.txt`. 0.9.11a1 removes the false errors but delivers `Any` rather than the promised var type on current pyright. No typing test in the repo asserts class-level access (`tests/units/vars/test_hybrid_property.py` only `isinstance`s at runtime).
- Also observed: a var fn `def _scaled_var(cls) -> rx.Var[int]: return cls.count * 3` reports `Type "int" is not assignable to return type "Var[int]"` because an unannotated `cls` types `cls.count` as `int` (plain annotation, no `rx.Field`). The repo's own tests carry `# pyright: ignore[reportReturnType]` on those lines, so this is known; the docs example (`docs/vars/hybrid_properties.md`) uses `rx.cond`, which avoids it.

### B. (low, pre-existing) Getter returning a list/dict yields a plain Python container on class access, not an `ArrayVar`/`ObjectVar`
`@hybrid_property def pair(self) -> list[str]: return [self.first, self.last]` => `State.pair`
is a `list` of Vars; `State.pair.length()` => `AttributeError: 'list' object has no attribute 'length'`
while the (older-pyright) typing promises `ArrayVar[list[str]]`. `rx.foreach(State.pair)` works.
Same for a dict getter (`dict`, indexing works). Identical in 0.9.10.post2 (`logs/probe_edges_*.txt`).
Type/runtime mismatch worth a docs note ("use a var function returning `Var.create([...])`").

### C. (low, pre-existing) Error quality when a getter cannot run against vars
- `bool(self.last)` / `x if self.count else y` => `VarTypeError: Cannot convert Var ... to bool ... use rx.cond` (good, but does not mention the hybrid property name or the `@name.var` escape hatch).
- `len(self.tags)` => raw `TypeError: object of type 'ArrayCastedVar' has no len()` with no reflex hint at all.
- `[t.upper() for t in self.tags]` => `VarTypeError: Cannot iterate over Var ... use rx.foreach` (good).
- Backend var in the getter => `HybridPropertyError` naming the property, the var and the fix (excellent).
Both versions behave the same (`logs/probe_none_var_*.txt`, `logs/probe_edges_*.txt`).

### D. (low, behavior change, by design) Var fn returning `None` is silent inside components
`rx.text(State.none_fe)` compiles to `null` (renders nothing), `rx.cond(State.none_fe, a, b)`
becomes `isTrue(null)` (always the false branch), an f-string `f"v={State.none_fe}"` bakes the
literal text **"v=None"** into the page, `rx.foreach` raises `ForeachVarError ... var 'null' of type NoneType`
(does not mention the property). 0.9.10.post2 fell back to the getter when the var fn returned
`None` (rendered `count`). The docs describe the `None` semantics, but nothing warns a user who
references such a property in a component. `logs/probe_none_var_smoke.txt`.

### E. (low, pre-existing) A single TYPE_CHECKING-only annotation on a dataclass makes every attribute of that dataclass inaccessible on the frontend, with a misleading error
`Weighted.weight: Unresolvable | None` (name only importable under `TYPE_CHECKING`) =>
`FwdState.weighted.name` fails at compile with
`VarAttributeError: The State var ... of type <class 'Weighted'> has no attribute 'name' or may have been annotated wrongly`
plus `Warning: Failed to resolve ForwardRefs for <class 'Weighted'>.name due to name 'Unresolvable' is not defined`
logged **4 times per access**. `name` is perfectly annotated; the culprit is another field.
Identical on 0.9.10.post2 and on 3.14 (`logs/dev_smoke_crash_fwd_unresolvable.log`, `logs/probe_fwd_mock_*.txt`).
Not the #6929 scope (which is about *unannotated* probes and is fixed), but adjacent.

### F. (info, pre-existing) State var annotated with a class defined later in the module fails at import
`items: list[Later] = []` with `from __future__ import annotations` and `Later` defined below the
state => `NameError: name 'Later' is not defined` from `_check_overridden_basevars` at class creation.
Same in 0.9.10.post2 (`scripts/probe_later_forward_ref.py`). Dataclass-internal forward refs
(`Item.tag: Tag | None` with `Tag` defined later) are fine.

### G. (info) `State.setvar("full", ...)` fails with `AttributeError: 'S' object has no attribute 'set_full'`
Same message for a base var (`setvar("first")` => no `set_first`) — `setvar` relies on the
auto-generated `set_*` handlers that are off by default; not hybrid-specific, both versions.

### Benign / noise seen
- prod: console `Failed to load resource: 404` = `/favicon.ico` (app has none; dev did not log it). `/robots.txt` 404 too.
- console `log` lines "Disconnect websocket on page navigation" on every route change (both modes).
- `DeprecationWarning: ArrayVar.foreach has been deprecated in version 0.9.7. Use ArrayVar.map` (my first version used `.foreach`; switched to `.map`) and `Implicit Radix Themes enablement has been deprecated` (added `rx.plugins.RadixThemesPlugin()`); `@rx.memo` without `rx.Var[...]` parameter annotations warns (0.9.3 deprecation). All pre-existing deprecations, not new.
- editing `core_state.py` while the dev server ran hot-reloaded correctly (backend restart + vite HMR; driver re-run passed).
- `reflex_base.vars.hybrid_property` is shadowed by the submodule of the same name on `reflex_base.vars` (attribute is the module, not the class) — cosmetic, both versions.
