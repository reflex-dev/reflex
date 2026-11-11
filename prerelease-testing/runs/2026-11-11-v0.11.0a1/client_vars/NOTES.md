# client_vars cluster — reflex 0.11.0a1 (2026-11-11)

## Status / resume here
- Working dir: `$SB/apps/client_vars/` (`SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`).
  Ports: frontend 3260-3279, backend 8260-8279. Venvs: shared `new` (0.11.0a1), `prev` (0.10.1), `driver`.
- Helper: `scripts/srv.sh start <label> <venv> <dev|prod> <appdir> <fport> <bport> [ENV=VAL...]` / `srv.sh stop <label>`
  (own process group, refuses busy ports, logs in `$W/logs/<label>.log`). Drivers run with
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/<driver>.py ...`.
- **FINISHED** (2026-11-11). Final report: `../reports/client_vars.md`. Issue list: section 7 below. Evidence: `evidence/`.
- Nothing left running; no venv to clean except the control `$SB/envs/client_vars-ctrl-a3` (reflex 0.10.0a3 from PyPI).
- Not done: see "Not covered" at the end.
- Sources are copied to `src/` here by `scripts/sync_dest.sh` (no `.web`, logs or results).

## 1. client_state (#6936)

### Offline probe (`src/probes/cs_probe.py`)
`cd $SB/apps/client_vars/probes && $SB/envs/new/bin/python -I cs_probe.py new`
- names validated (`naïve`, `my-var`, `""` rejected with a clear ValueError); `push`/`retrieve`/`global_value` on an unnamed var
  raise `ValueError: Cannot push a value: ... Give it a name -- rx.client_state("my_name") -- to make it global`.
  **That hint is wrong**: `rx.client_state("my_name")` is an UNNAMED var whose default is `"my_name"` (the first positional is
  `default`); the docstring of `ClientStateVar.create` repeats it (`rx.client_state("my_name")` is **global**). Following the
  hint reproduces the same error. Correct spelling: `rx.client_state(default, name="my_name")`. (ISSUE CV-2)
- `.set(lambda v: v + [3])` on a list var: `VarTypeError: Unsupported Operand type(s) for +: ArrayCastedVar, list` (ArrayVar + python
  list is unsupported in general, also 0.10.1); `.set(lambda a, b: ...)` -> clear VarTypeError.
- old keyword/positional signature on the new function (`rx.client_state(var_name="x", default=1)`) -> plain TypeError
  (unexpected keyword); `rx._x.client_state("n", 1, False)` still works + deprecation pointing at the caller's line.

### App `csapp` (pages `/`, `/other`, `/memo`, `/backend`, `/legacy`)
```
cd $SB/apps/client_vars
scripts/srv.sh start cs-dev new dev $PWD/csapp 3260 8260
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_cs.py http://localhost:3260 new-dev
scripts/srv.sh stop cs-dev
scripts/srv.sh start cs-prod new prod $PWD/csapp 3261 3261     # prod: one port
... drive_cs.py http://localhost:3261 new-prod
# flags: append CS_AUTO_MEMO=0 CS_COMPILER=1 to the start line (auto_memoize=False + react_compiler=True)
# CS_DUP_DIFF=1: the two `name="dup"` vars (shared.py / other_mod.py) get different defaults
```
| run | result |
|---|---|
| dev default | 91/91, console clean |
| prod default | 91/91, only the favicon 404 |
| dev `auto_memoize=False` + `react_compiler=True` | 91/91, console clean |
| prod `auto_memoize=False` + `react_compiler=True` | 91/91 |
| dev `CS_DUP_DIFF=1` | 91/91: the second default (`OTHER-default`) is silently ignored, first reader wins, no warning |
| dev `CS_DUP_DIFF=1` + `CS_AUTO_MEMO=0 CS_COMPILER=1` | **frontend 500**: `Identifier 'dupRxClientState' has already been declared` (ISSUE CV-3) |

What the 91 checks cover: named var read/written from two pages + the layout header; `.set` with value / lambda / FunctionVar;
event chains `[cs.set(...), State.handler]` in both orders; trigger-arg compound value; form `on_submit`; deprecated
`.set_value(v)` and `.set_value()`; page-owned unnamed vars reset on navigating away and back, named ones persist (also across
history back) and reset on a full reload; `@rx.memo` x3 independent; helper function called twice; `@rx.memo` rows in `rx.foreach`;
plain-lambda foreach rows (share one var, as documented); `rx.cond` branches (value survives branch unmount, page-owned);
`rx.ComponentState` instances (independent); backend `push` / `retrieve` from handlers, several pushes in one handler, complex
values (dict/list/None/unicode), background task push + retrieve, push-then-retrieve ordering, `rx.call_script` via
`refs["__client_state"]`, a value pushed before its only reader mounts, retrieve of a never-mounted var (`None`);
`rx._x.client_state` legacy page; a second tab (client state is per tab).

Render counts (custom `RenderProbe` component in `csapp/assets/render_probe.js`, counts its own commits in `window.__rc`):
5 writes to one unnamed var -> its 2 readers render 5x each, every other probe 0; 1 write to the named var -> its 2 readers
(page + header) 1x, others 0; a server delta re-renders only the state reader. Same numbers in dev/prod and with
`auto_memoize=False` + `react_compiler=True`. (First attempt used an impure counter expression in a prop: with the compiler
on that makes every probe re-render on every write, i.e. the compiler bails out on the page as its warning says. Not a bug.)

Quirks (not issues):
- `rx.form(on_submit=lambda data: cs.set(data["field"]))` -> `UntypedVarError` (form data is `Any`); `data.to(dict[str, str])["field"]` works.
- `@rx.memo` rows in `rx.foreach` keep their client state by INDEX: after deleting the first item the "open" flag stays on
  row 1, which now shows the next item. Passing `key=item` (memo declared with an `rx.RestProp`) makes the state follow the item
  (csedge `/keyed`). The docs example (`expanded = rx.client_state(False)  # one per rendered row`) does not mention keys.
- `mlist(items=..., id="x")` on a memo without RestProp raises TypeError, while `key=` only warns (deprecated since 0.9.3).

### App `csedge` (edge cases, one page each)
```
scripts/srv.sh start edge-dev new dev $PWD/csedge 3260 8260 [CS_PAGES=a,b] [CS_AUTO_MEMO=0 CS_COMPILER=1]
CS_PAGES=... NO_PROXY=... $SB/envs/driver/bin/python scripts/drive_edge.py http://localhost:3260 new-dev
```
- default dev 51/51 (+`/casing2` only on request), default prod 50/50, compiler prod 45/45; compiler dev 43/44 (first page hit
  vite's cold-start `504 Outdated Optimize Dep` and did not recover within 15 s; not reproduced on other pages).
- `/collapse`: page-level read lifts the var (documented). `/memoforeach`: an unnamed var created in a foreach body inside a memo is
  shared by the rows of one memo instance, separate per instance. `/statedefault`: `rx.client_state(State.v)` takes the state value
  only as the initial value. `/storagecollide`: a client var named like a LocalStorage key is independent of it.
  `/setcs`: `rx.client_state({"a", "b"})` is a SetVar on the client (`union`, `contains`, `foreach`).
- `/casing` + `/casing2` (`CS_PAGES=casing,casing2`): names `item` and `Item` both get the setter identifier `setItem`. Used
  from separate elements they work; attached to ONE element (`on_click=[lower.set("L"), upper.set("U")]`) the generated memo
  module `app_components/<app>/<app>.jsx` fails to parse (`Identifier 'setItem' has already been declared`) and, because every
  page imports that module, **every page of the app returns 500** (ISSUE CV-3).
- `/dupsame`, `/dupsame2`: two `name="shared_name"` vars with defaults `first` / `second`: both readers show `first`.

### Legacy API: `legacyapp` (written against 0.10.1, run unchanged on both)
`scripts/srv.sh start leg-<v> <v> dev $PWD/legacyapp 3262 8262; drive_legacy.py http://localhost:3262 <v>-dev` -> `results/legacy/<v>-dev_obs.json`
- Identical observations on 0.10.1 and 0.11.0a1 for global vars (set_value, on_change=.set, push, retrieve, dict values,
  navigation, reload, a var never included as a child, retrieve from a page where the var is not mounted).
- Only difference: `global_ref=False` vars. On 0.10.1 `local.set_value(local.value + 1)` had NO visible effect (span stayed `0`:
  each auto-memoized component got its own `useState`); on 0.11.0a1 it counts (`2`) and resets on remount. Improvement.
- 0.11.0a1 logs one deprecation per call site, each naming the user's file:line.

### reflex-examples `overkey` (uses `ClientStateVar.create("user_input", default="")`)
`scripts/srv.sh start ok-<v> <v> dev $PWD/overkey_<v> 3262 8262; drive_overkey.py http://localhost:3262 <v>-dev`
- 0.10.1: 6/6 (typing marks letters, wrong letter pink, caret, "Time's up!", WPM from the retrieved client value, restart clears).
- **0.11.0a1 unmodified: the app does not start** — `AttributeError: 'EventHandler' object has no attribute '__qualname__'` at
  class definition, from `@rx.event` stacked on `@rx.event(background=True)` (overkey.py `tick`). Minimal repro:
  `probes/stacked_event_probe.py` (prev: OK, new: AttributeError). (ISSUE CV-1; belongs to the events area, #7673.)
- 0.11.0a1 with the duplicate `@rx.event` removed (`overkey_new`, marked `PATCHED`): 6/6, console clean; 791 letters subscribed
  to one client var, 10 keystrokes painted in ~0.11 s.

## 2. SetVar (#7642)

### Offline probe (`src/probes/set_probe.py`), both versions
`cd probes && $SB/envs/new/bin/python -I set_probe.py new` (and `prev`); outputs in `results/set_probe_{new,prev}.txt` (scratch).
- 0.11.0a1: `set[str]`, `frozenset[int]`, `set[tuple[int,str]]`, `set[Enum]`, `set[str] | None`, bare `set`, computed vars, dataclass /
  pydantic fields, `dict[str, set[int]]["k"]`, `list[set[int]][0]` are all `SetVar`; literals render sorted
  (`[[1, "a"], [2, "b"]]`), mixed unsortable literals do not crash (`[null, 1, "x"]`).
- 0.10.1: all of those are `ArrayVar`; `frozenset` state vars are rejected (`VarTypeError ... serializable type`).
- 17 deprecated array operations each warn once per call site with the caller's `file:line`
  (`SetVar.__getitem__ has been deprecated in version 0.11.0. A set is not a sequence; call .to_array() first ...`).
- `tags + ["x"]` raises `VarTypeError: Unsupported Operand type(s) for +: ArrayCastedVar, list` on BOTH versions (ArrayVar + python
  list is unsupported), so it is not a new break; `lst + tags` works with the warning.
- `tags | {"x"}` / `tags & {"x"}` stay the generic logical or/and (typed `SetVar`), `==` compares by reference: documented in
  `docs/vars/var-operations.md`. `tags - {...}` / `tags ^ {...}` -> plain Python `TypeError: unsupported operand`.

### App `varsapp` `/` and `/setnone`
```
scripts/srv.sh start vars-dev new dev $PWD/varsapp 3260 8260 [PYTHONHASHSEED=n]
... drive_sets.py http://localhost:3260 new-dev          # add a third arg `old` when driving 0.10.1
scripts/srv.sh start vars-prod new prod $PWD/varsapp 3261 3261 VARS_NO_SETNONE=1
```
- 29 frontend results (union/intersection/difference/symmetric_difference/issubset/issuperset/isdisjoint/contains/length, tuples,
  enums, frozenset, computed set, dataclass + pydantic set fields, chained ops) equal Python's after each of 17 mutations
  (`add`, `discard`, `|=`, `symmetric_difference_update`, reassign, `clear`, in-place adds on dataclass/pydantic fields, ...):
  dev, prod, PYTHONHASHSEED 1/2/3. `rx.foreach(set)` and `foreach(set.to_array())` render exactly the JSON order.
- Baseline 0.10.1: `pairs.contains((1, "a"))` is `false` (compared by reference) -> fixed by SetVar.
- Order: the DOM order is Python's set iteration order; it is stable across deltas that do not touch the set, differs per
  `PYTHONHASHSEED` (`['c','b','a']` / `['a','b','c']`), and 1-2 of 13 mutations reorder surviving elements (rehash). Same as 0.10.1.
- **`rx.match(State.tags, ({"c", "d"}, ...))` is order-dependent**: it compiles to `JSON.stringify(tags)` vs
  `JSON.stringify(["c","d"])` (literal sorted). With `PYTHONHASHSEED=1` (and in the prod run with a random seed) the state set
  `{"c","d"}` serialises as `["d","c"]` and the case does NOT match (`match-default`). (ISSUE CV-5; 0.10.1 has the same shape.)
- A handler parameter annotated `set[str]` receives a `list` when a set var is passed (`State.take(State.tags)`), on both
  versions (ISSUE CV-6, low).
- `/setnone`: `maybe: set[str] | None = None` + `maybe.contains("m")` -> `TypeError: Cannot read properties of null (reading
  'some')` at `pySetHas`; dev: the page never hydrates; prod: **the production build fails** (`Prerender: Request failed for
  /setnone/`). 0.10.1 fails the same way with `reading 'includes'` (ISSUE CV-7, not a regression). `rx.foreach(maybe, ...)` is null-safe.

## 3. Unicode string ops (#7548): `varsapp` `/unicode`
`... drive_unicode.py http://localhost:3260 new-dev` (table in `results/unicode/<label>_table.json`)
- 0.11.0a1 dev + prod: `reversed()`, `length()`, `rx.foreach(str)`, slices, `[1]`, `[-1]`, `upper`/`lower` equal Python for ASCII,
  `a😀b`, the family ZWJ sequence, a flag, `e` + combining acute, thumbs-up + skin tone, CJK incl. U+20BB7, and typed input.
  Code points, not graphemes: the family emoji has length 5, foreach renders 👨, ZWJ, 👩, ZWJ, 👧 as separate spans, and
  `reversed()` gives 👧‍👩‍👨 (a different family); `"e\u0301a".reversed()` moves the accent onto the `a`; a flag reverses into
  another flag (`🇩🇪` -> `🇪🇩`).
- 0.10.1 baseline: `reversed()` and foreach split surrogate pairs (`b\ude00\ud83da`).
- Not covered by #7548: `StringVar.split()` / `.split("")` still split UTF-16 code units on both versions (`"a😀b".split()` ->
  `["a","\ud83d","\ude00","b"]`), so `rx.foreach(s.split(), ...)` (the pattern overkey uses) still breaks astral characters
  while `rx.foreach(s, ...)` does not (ISSUE CV-8, low).

## 4. Storage declarations (#7582, STATE-22/23)

### Offline probe (`src/probes/storage_decl_probe.py`), both versions
`cd probes && $SB/envs/<venv>/bin/python -I storage_decl_probe.py <venv>` (outputs in scratch `results/storage_decl_{new,prev}.txt`)
- Unchanged and working on both: `x: str = rx.LocalStorage("a")`, `x: rx.LocalStorage = rx.LocalStorage("a")`,
  `x: str = rx.Cookie("c", max_age=60, path="/p")`, `x: rx.Cookie = rx.Cookie()`, `x: str = rx.SessionStorage("s")`,
  annotation-only `x: rx.LocalStorage`, `x: rx.LocalStorage = "plain"`, `rx.field(rx.LocalStorage("a"))`, `rx.Field[str]`,
  `Annotated[str, ...]`, `str | None`, `int` / `set[str]` / `list[str]` annotations with a storage default, `name=` + `sync=True`,
  a mixin with a storage default.
- Now `VarTypeError` at compile (0.10.1: silently an ordinary var, or storage with the factory ignored):
  `rx.field(default_factory=lambda: rx.LocalStorage("a"))` on `str`, `str | None`, `Literal[...]`, `Annotated[str, ...]`; the same with
  `rx.Cookie` / `rx.SessionStorage`; a storage-annotated var with ANY factory (`default_factory=rx.LocalStorage`, `lambda: "plain"`);
  on a parent state, in a mixin, in an `rx.ComponentState`.
  Message: `Browser storage var 'State.theme' cannot use a default_factory. Declare the storage as the default value instead, such
  as `theme: str = rx.LocalStorage("", name='theme')`.` Names the var and the fix (the suggested line drops the factory's default
  and options such as `max_age`, and always says `str`). The traceback has no frame in the user's file (raised from the compiler).
- **Still silent on 0.11.0a1** (residual STATE-22): a storage-producing factory on a var that cannot hold a `str`:
  `x: int = rx.field(default_factory=lambda: rx.LocalStorage("5"))` and `x: list[str] = rx.field(default_factory=...)` compile and
  stay ordinary vars, although `x: int = rx.LocalStorage("5")` IS storage (ISSUE CV-9, low).
- Side effect of the check: every `default_factory` on a str-compatible frontend var is now called once more, at compile time
  (`plain factory calls`: 0.10.1 = 1, 0.11.0a1 = 2). A factory that raises at compile is skipped silently (by design).
- `pydantic.Field(...)` as an rx.State default is not understood on either version (the FieldInfo object becomes the value).

### Real compile: `errapp` (`scripts/run_errapp.sh <venv> [case...]`, one misuse per `ERR_CASE`)
| case | 0.10.1 | 0.11.0a1 |
|---|---|---|
| `storage_factory`, `storage_factory_cookie` | compiles (ordinary var) | `VarTypeError` above, exit 1 |

## 5. Var errors (#7648, #7651; STATE-10)

Offline probe `src/probes/var_errors_probe.py` (both versions, scratch `results/var_errors_{new,prev}.txt`) + `errapp`.

### #7648 `@property` through a state Var
- 0.11.0a1 raises `VarAttributeError` for a plain `@property` on a pydantic model, a subclass (inherited), a dataclass (+inherited),
  `list[Model][0].prop`, inside `rx.foreach`, `Model | None`, `dict[str, DC]["k"].prop`, an `rx.Model`, a SQLAlchemy
  `MappedAsDataclass` model. Message names the property, the class and the fix:
  `The property 'full' on Pydantic model 'Person' is not included in serialized state. Use `@pydantic.computed_field` ...` /
  `The property 'label' on dataclass 'Item' ... register an `rx.serializer` for the dataclass to include it.`
  `reflex compile` prints the full traceback incl. the user's `errapp.py, line N, in index` and `Happened while evaluating page 'index'`.
- Still allowed: `@pydantic.computed_field`, a model overriding `model_dump`, a model with a registered `rx.serializer`.
- 0.10.1: all of them compiled (rendered empty). All are covered by the reflex-base Breaking Changes entry.
- `functools.cached_property` and methods get the older generic message (`has no attribute 'cached' or may have been annotated
  wrongly`) on both versions.

### #7651 backend var misuse (re-verification of STATE-10)
Now `BackendVarFormatError: Backend var 'State._secret' exists only on the server ... Use State._secret.default_value() ...,
declare it as ClassVar[...] ..., or use a regular state var ...` (0.10.1 in brackets):
`rx.toast(...)`, `rx.image(src=)`, `rx.input(value=)`, style / `color=` / `class_name=` / `custom_attrs` / `key=` (all: `TypeError:
Unsupported type Field for LiteralVar`), `rx.box(id=)` (`TypeError: expected string or bytes-like object, got 'Field'`),
`rx.Var.create(...)` incl. inside list/dict/tuple, `rx.cond` / `rx.match` / `rx.foreach`, `rx.redirect` / `set_clipboard` /
`console_log` / `window_alert` / `call_script` / `download`, `str()` / `%` / `!s` (returned the `Field(default='secret', ...)` repr),
`app.add_page(title= / description= / image=)` and `@rx.page(title=)` (`ChildrenTypeError: Component Title received child
Field(...)` at compile).
Unchanged, still cryptic or silent on 0.11.0a1 (same as 0.10.1; ISSUE CV-10):
- child: `rx.text(State._secret)` -> `ChildrenTypeError: Component Text received child Field(default='s3cr3t-default', is_var=True,
  annotated_type=<class 'str'>) of type <class '...Field'>` (prints the default value, names neither the var nor a fix)
- typed props: `rx.el.div(title=State._secret)`, `rx.link(href=...)`, `add_page(meta=[{"content": State._secret}])` ->
  `TypeError: Invalid var passed for prop Div.title, expected type Var[str], got value Field(default=...)`
- event args: `State.take(State._secret)` -> `EventHandlerTypeError: Arguments to event handlers must be Vars or
  JSON-serializable. Got Field(default=...)`
- silent: `State._secret == "x"` is a plain `False`, so `rx.cond(State._secret == "s3cr3t-default", A, B)` compiles and always
  shows B; `bool(State._secret)` is `True`; `app.add_page(on_load=State._secret)` compiles (exit 0).
- `app.add_page(route=State._secret)` -> `AttributeError: 'Field' object has no attribute 'strip'`.
Server-side fallout of the `str()` change: `print(State._secret)` and `logging.info("%s", State._secret)` now raise
`BackendVarFormatError` ("cannot be used in the UI") where 0.10.1 printed the Field repr; logging swallows it as
`--- Logging error ---`. `repr()` / `!r` still work. `str(State.get_fields()["v"])` (frontend var) now raises
`'S.v' is the field of a state var, not the var. Use S.v to use it in the UI.`

## 6. Storage at runtime (#7637, #7652; HYD-08/09/12/13)

### App `stapp` + three tabs (`scripts/drive_storage.py`)
```
scripts/srv.sh start st-new new dev $PWD/stapp 3260 8260      # prev: ports 3262 8262; prod: `new prod ... 3261 3261`
NO_PROXY=... $SB/envs/driver/bin/python scripts/drive_storage.py http://localhost:3260 new-dev   # obs JSON: results/storage/<label>_obs.json
```
Vars: `a`, `b` (state `St`), `c` (substate `Sub`), `d` (other state `Other`) all `rx.LocalStorage(..., name="shared", sync=True)`;
`solo` / `unnamed_sync` (sync), `mixed_sync` + `mixed_nosync` (one name, one synced), plain / `rx.LocalStorage`-annotated /
int-annotated LocalStorage, SessionStorage, cookies (`max_age=5`, `max_age=30`, `path="/sub"`, `rx.Cookie`-annotated),
computed vars `len(self.solo)` and `self.a.upper()`.

| check | 0.10.1 dev (control) | 0.11.0a1 dev | 0.11.0a1 prod |
|---|---|---|---|
| fresh profile writes nothing | pass | pass | pass |
| #7637 tab A sets `a`: `b`/`c`/`d` in tab A | stay at their defaults (HYD-13) | all `A1` | all `A1` |
| write through `Other.d` / `Sub.c` / a background task | writing tab keeps stale siblings | every var in every tab follows | same |
| `a="both-A"`, `b="both-B"` in ONE event | A: `a=both-A b=both-B c,d stale`; B/C + storage `both-A` | A: `b=both-B`, rest `both-A`; B/C + storage `both-A` | same |
| #7652 `localStorage.clear()` typed in tab A | B/C keep the old values | B/C reset every synced var to its default, computed vars recompute; tab A itself keeps its values (no storage event in the originating tab) | same |
| `localStorage.removeItem("solo")` in tab B | A/C keep `solo-2` | A/C -> `solo-default`; B keeps `solo-2` | same |
| `rx.remove_local_storage("solo")` from A | B/C keep `solo-3`; server log `TypeError: object of type 'NoneType' has no len()` from `solo_len` (HYD-12), 4x | B/C and A -> default, no error in the log | same |
| `rx.remove_local_storage("shared")`, `rx.clear_local_storage()` | no reset | each var back to ITS OWN default in every tab; localStorage stays empty | same |
| cookies | `ck` ttl 3.7 s, `ck30` 26.7 s, `ck_path` path `/sub` (value visible on `/sub` only), expired cookie -> default after 6 s | identical | identical |
| checks | 12/24 | 23/24 (the 1 = the INFO row "conflicting writes") | 23/24 |

Server log on both versions: `Expected field 'St.num' to receive type '<class 'int'>', but got '5' of type '<class
'...LocalStorage'>'` once per state instantiation for the int-annotated LocalStorage var (known, R101-15, unchanged).
0.10.1 additionally logs `Expected field 'St.a' ...` when a `null` is synced in; 0.11.0a1 does not.
STATE-23 (`scripts/drive_state23.py`): setting and re-hydrating `typed: rx.LocalStorage` / `ck_typed: rx.Cookie` logs nothing on
0.10.1 or 0.11.0a1 -> not reproducible here, so no statement about a fix.

### Hydration fixtures on this cluster's ports (`scripts/run_hyd_fixtures.sh`, output `evidence/hyd_fixtures_storm_stamp.txt`)
Control `client_vars-ctrl-a3` = `reflex[db]==0.10.0a3` from PyPI (`cd $SB && uv --no-config venv ...; uv --no-config pip install
--prerelease=allow --only-binary :all: 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3'`).
| run | control 0.10.0a3 | 0.11.0a1 dev | 0.11.0a1 prod |
|---|---|---|---|
| `run_storm.sh <v> dev 3 3264 8264 S 6` | storms 2/2 (36k-177k frames, tabs split `s2`/`s3`) | 0/3, 69-81 frames, all 7 tabs + localStorage `s5` | 0/3, 97-101 frames |
| `run_stamp2.sh <v> dev 3264 8264 3 1 6` | run 1: 2.06 M frames, not converged; run 2: driver timed out | 0/3 storm, 89-205 frames, one value in 6 tabs; `/same` 47 frames | 0/3, 102-125 frames; `/same` 50 |
`state.js` md5 on 0.11.0a1: `04397de7` (0.10.0: `b7915eda`), i.e. the sync code changed (#7637/#7652) and stays storm-free.

## 7. Issues (details and repro in the sections above)
| id | title | severity | regression |
|---|---|---|---|
| CV-1 | `@rx.event` stacked on `@rx.event(...)` raises `AttributeError: 'EventHandler' object has no attribute '__qualname__'` at class definition; reflex-examples `overkey` does not start | high | yes |
| CV-2 | "Give it a name -- rx.client_state("my_name")" (error text + `create` docstring) shows the wrong call | low | no (new API) |
| CV-3 | client state identifiers collide: names differing in first-letter case share a setter (`setItem`) -> generated module fails to parse, every page 500; one name with two defaults -> silently first wins, or `Identifier ... already declared` with `auto_memoize=False` | low | no (new API) |
| CV-4 | docs: per-row client state in `rx.foreach` follows the index unless the memo gets `key=` | low | no |
| CV-5 | `rx.match` on a set compares order-dependent JSON; result depends on `PYTHONHASHSEED` | low | no |
| CV-6 | handler parameter annotated `set[str]` receives a `list` | low | no |
| CV-7 | `set[str] \| None` var that is `None`: `contains`/`union`/`issubset` throw in the browser and fail the prod prerender | low | no |
| CV-8 | `StringVar.split()` / `.split("")` still split UTF-16 code units | low | no |
| CV-9 | #7582 leaves a storage-producing `default_factory` on `int` / `list[str]` vars silently ordinary | low | no |
| CV-10 | #7651 leaves backend var as child / typed prop / event arg cryptic, and `State._x == ...` silently `False` | low | no |

## Not covered
- client_state: dev hot reload with client values; `auto_memoize=False` WITHOUT `react_compiler`; SSR-only / embedded second app;
  `global_set` handed to a real non-React library; Firefox/WebKit.
- SetVar: `rx.data_table` fed by a set, sets of dataclass/pydantic elements, `set[datetime]`, a LocalStorage-backed `set[str]` at
  runtime (compiles as storage; value is a str).
- Storage: prod + Redis legs, the 100 ms RTT / raw-CDP verifier families (`vmatrix.sh`), Cookie `secure` / `same_site` / `domain`,
  `sessionStorage.clear()`.
- Var errors: `rx.upload(on_upload_progress=State._x)`, hybrid properties, pydantic v1 models.
