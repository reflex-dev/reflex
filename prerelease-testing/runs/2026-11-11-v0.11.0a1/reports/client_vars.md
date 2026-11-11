CLUSTER: client_vars
SUMMARY: The features in this cluster work as their changelog lines say, in dev and prod Chromium: `rx.client_state` (named/unnamed scoping, push/retrieve, render isolation, also with `auto_memoize=False` + `react_compiler=True`), `SetVar` (29 frontend results equal Python's after each of 17 mutations), storage declaration errors (#7582), shared-name sync and cross-tab clear (#7637, #7652), the `@property` and backend-var errors, and code-point string ops. One regression found, outside the cluster's own PRs: any `@rx.event` stacked on another `@rx.event(...)` now raises `AttributeError` at class definition, so the reflex-examples `overkey` app (the ClientStateVar example) does not start on 0.11.0a1. The other nine issues are low severity: a wrong API hint in a client_state error, generated-identifier collisions, and gaps that 0.10.1 has too. HYD-08/09/12/13 are fixed against reproducing controls.
ARTIFACTS: /home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/client_vars/ (NOTES.md, src/ = apps + probes + scripts, evidence/)

Paths below: `$SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`, `W=$SB/apps/client_vars` (same tree as `client_vars/src/`), `NP="NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"`, `DRV=$SB/envs/driver/bin/python`. `scripts/srv.sh start <label> <venv> <dev|prod> <appdir> <fport> <bport> [ENV=VAL...]` / `srv.sh stop <label>`. Procedural: the very first sanity command of the session ran `python -c "import reflex"` with the checkout as cwd and printed the checkout path; nothing was derived from it, and every probe and app after that ran from `$SB` with a venv assertion.

TESTS:
- [pass] client_state app `csapp` (5 pages, 91 checks): 91/91 in dev, prod, dev + prod with `auto_memoize=False` + `react_compiler=True`. Covers a named var across two pages and the layout header, `.set` with value / lambda / FunctionVar, chains with a server event in both orders, form `on_submit`, deprecated `.set_value`, page-owned vars reset on navigating away and back while named ones persist, `@rx.memo` x3, memo rows in `rx.foreach`, `rx.cond` branches, `rx.ComponentState`, push/retrieve from handlers and a background task, complex values, a value pushed before its reader mounts, `rx._x.client_state`, a second tab. Console clean (prod: favicon 404 only).
- [pass] render isolation (custom `RenderProbe` component counting its own commits): 5 writes to one var re-render its 2 readers 5 times and every other probe 0 times; a named write re-renders only its readers on the page and in the header; a server delta re-renders only the state reader. Same counts in all four configurations.
- [pass] client_state edge app `csedge`: 51/51 dev, 50/50 prod, 45/45 prod with the compiler; page-level read lifts a memo var (documented), `rx.cond` / `rx.match` / style / `rx.foreach` over client values, default taken from a state var, `on_mount` setter, `global_set` / `global_value`, a client var named like a LocalStorage key, a set held in client state.
- [anomaly] `csedge` dev with `auto_memoize=False` + `react_compiler=True`: 43/44; the first page loaded after a cold start hit vite's `504 Outdated Optimize Dep` and did not hydrate within 15 s. Not reproduced on the other pages or in prod.
- [pass] legacy API app `legacyapp` (written for 0.10.1, unchanged): same observations on 0.10.1 and 0.11.0a1 for global vars; `global_ref=False` vars, whose `set_value` had no visible effect on 0.10.1, now work. One deprecation per call site, each with the user's file:line.
- [fail] reflex-examples `overkey` unmodified on 0.11.0a1: does not start (issue 1). On 0.10.1: 6/6.
- [pass] `overkey` with the duplicate `@rx.event` removed on 0.11.0a1: 6/6 (typing, wrong-letter highlight, timer, WPM from the retrieved client value, restart clears the input); 791 letters subscribed to one client var, 10 keystrokes painted in about 0.11 s.
- [pass] SetVar app `varsapp` `/`: 29 results (all nine operations, tuples, enums, frozenset, computed set, dataclass and pydantic set fields, chains) equal Python's after each of 17 mutations; dev, prod, `PYTHONHASHSEED` 1/2/3. `rx.foreach(set)` and `foreach(set.to_array())` render the JSON order. On 0.10.1 `pairs.contains((1, "a"))` is `false`; fixed by SetVar.
- [pass] SetVar deprecations: 15 array operations at 18 call sites each warn once per call site with the caller's file:line and still work. `tags + ["x"]` raises `VarTypeError` on both versions (ArrayVar + Python list is unsupported), so it is not a new break.
- [anomaly] set ordering: the DOM order is Python's set iteration order; stable across unrelated deltas, different per `PYTHONHASHSEED`, and 1-2 of 13 mutations reorder surviving elements. Same on 0.10.1.
- [pass] #7582 declarations (offline probe, 36 shapes, both versions): every storage-default and storage-annotation shape still works; a storage-producing or storage-annotated `default_factory` now raises `VarTypeError: Browser storage var 'State.theme' cannot use a default_factory. Declare the storage as the default value instead, such as `theme: str = rx.LocalStorage("", name='theme')`.` on str, `str | None`, `Literal`, `Annotated`, parent states, mixins and ComponentState. `reflex compile` exits 1 with that message.
- [anomaly] #7582 side effect: every `default_factory` on a str-compatible frontend var is called once more, at compile time (probe counter: 0.10.1 = 1 call, 0.11.0a1 = 2).
- [pass] #7637 / #7652 app `stapp`, three tabs: 23/24 dev and prod on 0.11.0a1 (the 24th is an informational row), 12/24 on 0.10.1. Writing tab updates same-name vars, also through a substate var, a var of another state class and a background task; `localStorage.clear()` / `removeItem` in one tab and `rx.remove_local_storage` / `rx.clear_local_storage` reset the other tabs' synced vars to each var's own default; computed vars recompute; no error in the server log.
- [anomaly] `a = "both-A"; b = "both-B"` (two vars, one storage name) in one event: the writing tab shows `b = both-B` while localStorage and the other tabs hold `both-A`.
- [pass] cookies: `max_age=5` expires in 3.7 s, `max_age=30` in 26.7 s, `path="/sub"` stored with that path and read only on `/sub`; identical on 0.10.1.
- [pass] hydration fixtures on ports 3264/8264/3265: `run_storm.sh` 0/3 storms dev and prod, `run_stamp2.sh` 0/3 dev and prod; the 0.10.0a3 control storms (see REVERIFIED).
- [pass] #7648: plain `@property` on a pydantic model, dataclass, `rx.Model` and `MappedAsDataclass` model (also inherited, `list[M][0]`, in `rx.foreach`, `M | None`, dict value) raises `VarAttributeError` naming the property, the class and the fix; `@pydantic.computed_field`, a `model_dump` override and a registered `rx.serializer` stay allowed. All compiled on 0.10.1; covered by the reflex-base Breaking Changes entry.
- [pass] #7651: 38 probed misuse paths raise `BackendVarFormatError` naming `State._secret` and three fixes (3 did on 0.10.1), including `str()`, `%`, `!s`, `rx.box(id=)`, `rx.toast`, `rx.image(src=)`, `rx.cond` / `rx.match` / `rx.foreach` and `add_page(title= / description= / image=)`. `reflex compile` shows the user's file and line in the traceback.
- [anomaly] #7651 fallout in server code: `print(State._secret)` and `logging.info("%s", State._secret)` now raise `BackendVarFormatError` ("cannot be used in the UI"); 0.10.1 printed the Field repr. Logging turns it into `--- Logging error ---`. The changelog lists this under Bug Fixes.
- [pass] #7548 `varsapp` `/unicode`: `reversed()`, `length()`, `rx.foreach(str)`, slices, indexing, upper/lower equal Python for an emoji, the family ZWJ sequence, a flag, a combining accent, a skin-tone modifier, CJK incl. U+20BB7 and typed input; 20/20 in dev and in prod. 0.10.1 splits surrogate pairs. Code points, not graphemes: the family emoji has length 5 and reverses into a different family.

REVERIFIED:
- HYD-08: fixed — `run_storm.sh new dev 3 3264 8264 S 6`: 0/3 storms, 69-81 frames, 7 tabs + localStorage on `s5` (prod 0/3); control 0.10.0a3 (`client_vars-ctrl-a3`, PyPI) storms 2/2 with 36k-177k frames.
- HYD-09: fixed — `run_stamp2.sh new dev 3264 8264 3 1 6`: 0/3 storms, 89-205 frames, one value in 6 tabs (prod 0/3); control 0.10.0a3 run 1: 2.06 M frames, not converged.
- HYD-12: fixed — 0.10.1 control logs `TypeError: object of type 'NoneType' has no len()` 4 times from the dependent computed var; 0.11.0a1 resets the var to its default in every tab with no error.
- HYD-13: fixed — 0.10.1 control: tab A sets `a`, its `b`/`c`/`d` stay at defaults; 0.11.0a1: all four show `A1` in all three tabs.
- STATE-10: changed — `str()` / `%` / `!s`, `rx.box(id=)` and `add_page` metadata now raise `BackendVarFormatError`; child, typed-prop and event-arg paths are unchanged (issue 10).
- STATE-22: changed — a storage-producing factory on a str-compatible var now fails at compile; on `int` / `list[str]` vars it is still silently an ordinary var (issue 9).
- STATE-23: changed — not reproducible on 0.10.1 or 0.11.0a1 with `scripts/drive_state23.py` (set and re-hydrate `typed: rx.LocalStorage`, `ck_typed: rx.Cookie`: no log line); no reproducing control, so no statement about a fix.

ISSUES:
- TITLE: `@rx.event` stacked on `@rx.event(...)` raises AttributeError at class definition; reflex-examples `overkey` does not start
  SEVERITY: high
  REGRESSION: yes
  REPRO: `cd $W/probes && $SB/envs/new/bin/python -I stacked_event_probe.py new` (and `prev`). Three class-body variants: `@rx.event` over `@rx.event(background=True)`, `@rx.event` over `@rx.event`, `@rx.event(background=True)` over `@rx.event`. Real app: copy `$SB/downloads/reflex-examples/overkey` and `reflex run` it with `$SB/envs/new` (its `tick` handler has `@rx.event` above `@rx.event(background=True)`).
  EVIDENCE: 0.10.1: all variants define the class. 0.11.0a1: `AttributeError: 'EventHandler' object has no attribute '__qualname__'. Did you mean: '__set_name__'?` raised at `reflex_base/utils/format.py:448` (`get_event_handler_parts`) for the first two, `TypeError: Background task must be async function or generator.` for the third. The changelog says a decorator stacked above `@rx.event` "still runs and registers under its own name, with a deprecation warning". `evidence/overkey_new_unpatched_tail.log`. This belongs to the events area (#7673); found here through `overkey`.
- TITLE: client_state "Give it a name -- rx.client_state("my_name")" hint and the `create` docstring show a call that does not name the var
  SEVERITY: low
  REGRESSION: no
  REPRO: `cd $W/probes && $SB/envs/new/bin/python -I cs_probe.py new | tail -6`. `rx.client_state("x").push(1)` raises the hint; `rx.client_state("my_name")` is an unnamed var whose default is `"my_name"`, so following the hint raises the same error. The working call is `rx.client_state("", name="my_name")`.
  EVIDENCE: `ValueError: Cannot push a value: this client state var is scoped to the component tree that uses it. Give it a name -- rx.client_state("my_name") -- to make it global and addressable.`; hook of the hinted call: `useClientState("my_name", "cs$12")`; docstring line: ``- ``rx.client_state("my_name")`` is **global**.`` (`reflex_base/client_state.py`, `_NOT_GLOBAL_MSG` and `ClientStateVar.create`).
- TITLE: client_state generated identifiers collide (names differing in first-letter case; one name with two defaults)
  SEVERITY: low
  REGRESSION: no
  REPRO: (a) `scripts/srv.sh start edge new dev $W/csedge 3260 8260 CS_PAGES=casing,casing2`, open `/casing`: `rx.client_state("lower", name="item")` and `rx.client_state("upper", name="Item")` with `on_click=[lower.set("L"), upper.set("U")]` on one button. (b) `scripts/srv.sh start cs new dev $W/csapp 3260 8260 CS_DUP_DIFF=1` (two modules declare `name="dup"` with different defaults), then the same with `CS_AUTO_MEMO=0 CS_COMPILER=1`.
  EVIDENCE: (a) `GET /app_components/csedge/csedge.jsx -> 500`, `[PARSE_ERROR] Identifier `setItem` has already been declared`; every page imports that module, so `/casing` shows "Application Error" and `/` renders empty (`evidence/casing_evidence.txt`). (b) default config: 91/91, the second default is ignored without a warning; with `auto_memoize=False`: `GET / -> 500`, `Identifier 'dupRxClientState' has already been declared` (`evidence/dup_default_auto_memo_off_error.txt`). Nothing is checked in Python at `rx.client_state(...)` time.
- TITLE: docs: per-row client state in `rx.foreach` follows the row index, not the item, unless the memo gets a `key`
  SEVERITY: low
  REGRESSION: no
  REPRO: `csapp` `/memo`: toggle row `b` open, click "del-first". `csedge` `/keyed` is the same list with `krow(item=item, key=item)` and an `rx.RestProp` parameter.
  EVIDENCE: without key: rows `['b', 'c', 'r3']` show `['closed', 'open', 'closed']` (the open flag moved to `c`); with key: `[('b', 'open'), ('c', 'closed')]`. `docs/wrapping-react/overview.md` shows `expanded = rx.client_state(False)  # one per rendered row` with `rx.foreach(State.items, lambda item: row(item=item))` and does not mention keys.
- TITLE: `rx.match` on a set compares order-dependent JSON, so a matching case is missed depending on `PYTHONHASHSEED`
  SEVERITY: low
  REGRESSION: no
  REPRO: `scripts/srv.sh start vars new dev $W/varsapp 3260 8260 PYTHONHASHSEED=1; $NP $DRV scripts/drive_sets.py http://localhost:3260 new-dev-s1`. The page has `rx.match(S.tags, ({"only"}, ...), ({"c", "d"}, ...), default)`; "copy-other" sets `tags = {"c", "d"}`.
  EVIDENCE: seed 1 and the prod run (random seed): `tags JSON order=['d', 'c'] match=match-default`; seeds 2, 3: `match-cd`. Compiled as `switch (JSON.stringify(tags)) { case JSON.stringify(["c", "d"]): ...`. 0.10.1 has the same shape. `evidence/sets_match_and_args.txt`.
- TITLE: an event handler parameter annotated `set[str]` receives a `list`
  SEVERITY: low
  REGRESSION: no
  REPRO: `varsapp` `/`: `on_click=S.take_set(S.tags.union(S.other))` (or `S.take_set(S.tags)`), handler `def take_set(self, v: set[str])` stores `type(v).__name__`.
  EVIDENCE: `#taken` shows `list:['a', 'b', ...]` on 0.11.0a1 and on 0.10.1; a handler calling `v.add(...)` would raise.
- TITLE: operations on a `set[str] | None` var that is `None` throw in the browser and fail the production build
  SEVERITY: low
  REGRESSION: no
  REPRO: `scripts/srv.sh start v new prod $W/varsapp 3261 3261` (page `/setnone`: `maybe: set[str] | None = None`, `S.maybe.contains("m")`, `.union({"z"})`, `.issubset({"z"})`); dev: open `/setnone`.
  EVIDENCE: prod: `TypeError: Cannot read properties of null (reading 'some')` at `pySetHas`, `Error: Prerender: Request failed for /setnone/`, `script "export" exited with code 1`; dev: the page never hydrates. 0.10.1 fails the same way with `reading 'includes'`. `rx.foreach(maybe, ...)` is null-safe. `evidence/setnone_prerender_vars-prod.txt`, `..._vars-prev-prod.txt`.
- TITLE: `StringVar.split()` / `.split("")` still split UTF-16 code units, unlike `rx.foreach` over the string
  SEVERITY: low
  REGRESSION: no
  REPRO: `varsapp` `/unicode` with `$NP $DRV scripts/drive_unicode.py http://localhost:3260 new-dev`.
  EVIDENCE: `"a😀b".split()` renders `["a","\ud83d","\ude00","b"]` (4 parts) while `rx.foreach(s, ...)` yields 3 characters; same on 0.10.1. `overkey` iterates letters with `rx.foreach(word.split(), ...)`. `evidence/unicode_table_new-dev.json` (`split_is_codepoints: false`).
- TITLE: #7582 still lets a storage-producing `default_factory` on an `int` / `list[str]` var compile as an ordinary var
  SEVERITY: low
  REGRESSION: no
  REPRO: `cd $W/probes && $SB/envs/new/bin/python -I storage_decl_probe.py new | grep -E "x: (int|list\[str\]) = rx.field"`.
  EVIDENCE: `[ok] x: int = rx.field(default_factory=lambda: rx.LocalStorage('5')): storage=NONE (ordinary var)`, same for `list[str]`, while `x: int = rx.LocalStorage('5')` gives `storage={'local_storage': ...}`. The check only runs for annotations that can hold a `str` (`reflex/compiler/utils.py`, `_may_hold_str`).
- TITLE: #7651 leaves backend var as a child, typed prop or event argument with the old cryptic errors, and `State._x == ...` silently `False`
  SEVERITY: low
  REGRESSION: no
  REPRO: `cd $W && scripts/run_errapp.sh new backend_child backend_typed_prop backend_event_arg backend_eq page_meta page_on_load` (one misuse per `ERR_CASE` in `errapp/errapp/errapp.py`).
  EVIDENCE: `rx.text(State._secret)` -> `ChildrenTypeError: Component Text received child Field(default='s3cr3t-default', is_var=True, annotated_type=<class 'str'>) of type <class 'reflex_base.vars.base.Field'>`; `rx.el.div(title=State._secret)` and `add_page(meta=[{"content": State._secret}])` -> `TypeError: Invalid var passed for prop Div.title` (resp. `Meta.content`)`, expected type Var[str], got value Field(default=...)`; `State.take(State._secret)` -> `EventHandlerTypeError ... Got Field(default=...)`. None names the var or a fix, and each prints the default value. `rx.cond(State._secret == "s3cr3t-default", A, B)` and `add_page(on_load=State._secret)` compile with exit 0; the cond always renders B. Identical on 0.10.1 (`evidence/var_errors_{new,prev}.txt`).

NOT_COVERED: client_state under dev hot reload, `auto_memoize=False` without `react_compiler`, `global_set` handed to a real non-React library, Firefox/WebKit. SetVar in `rx.data_table`, sets of dataclass / pydantic / datetime elements, a LocalStorage-backed `set[str]` at runtime (it compiles as storage). Storage with prod + Redis, the 100 ms RTT and raw-CDP verifier families (`vmatrix.sh`), Cookie `secure` / `same_site` / `domain`, `sessionStorage.clear()`. `rx.upload(on_upload_progress=State._x)`, hybrid properties, pydantic v1 models. The 0.10.1 keystroke timing of `overkey` was not recorded, so there is no typing-latency comparison. Time went to the breadth of the cluster; none of these was attempted and abandoned.
