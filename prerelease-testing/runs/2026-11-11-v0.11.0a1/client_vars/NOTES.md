# client_vars cluster — reflex 0.11.0a1 (2026-11-11)

## Status / resume here
- Working dir: `$SB/apps/client_vars/` (`SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`).
  Ports: frontend 3260-3279, backend 8260-8279. Venvs: shared `new` (0.11.0a1), `prev` (0.10.1), `driver`.
- Helper: `scripts/srv.sh start <label> <venv> <dev|prod> <appdir> <fport> <bport> [ENV=VAL...]` / `srv.sh stop <label>`
  (own process group, refuses busy ports, logs in `$W/logs/<label>.log`). Drivers run with
  `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/<driver>.py ...`.
- DONE: client_state (csapp, csedge, legacyapp, overkey), SetVar + unicode (varsapp, probes/set_probe.py).
- IN PROGRESS: storage (declarations probe, multi-tab app, hydration fixtures storm/stamp).
- TODO: var error probes (#7648, #7651), final report `reports/client_vars.md`.
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
