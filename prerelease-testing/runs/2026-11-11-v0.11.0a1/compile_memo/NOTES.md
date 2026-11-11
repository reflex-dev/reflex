# compile_memo cluster — reflex 0.11.0a1 (vs 0.10.1)

Run any app: `cd <app> && REFLEX_TELEMETRY_ENABLED=false $SB/envs/compile_memo-new/bin/reflex run --frontend-port 3300 --backend-port 8300`
(prod: `--env prod --frontend-port 3300 --backend-port 3300` with `REFLEX_API_URL=http://localhost:3300`; or `scripts/srv.sh`).
Rebuild the venvs: `uv --no-config venv $SB/envs/compile_memo-new --python 3.12 && uv --no-config pip install --python
$SB/envs/compile_memo-new/bin/python --only-binary :all: -r reqs/new.txt plotly` (prev: `reqs/prev.txt`; lucide-1.1.1 variant:
`reqs/new_l111.txt`). The 0.10.1 copy of `cm` is the same `cm/cm.py` (runs on both).

## Status / resume here
- DONE. Report: `../reports/compile_memo.md`. All servers stopped. Full logs/builds stay in `$SB/apps/compile_memo/`
  (`logs/`, `results/`, `builds/`); this dir holds sources, scripts, result JSON and evidence screenshots.
- Not covered: HYD-15 with `--backend-only`, R101-01/02, React Compiler bailout counting (R101-08), Windows.

`SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`
Ports: frontend 3300-3319, backend 8300-8319.

## Setup
- Own venvs (PyPI only, built from the shared envs' `pip freeze` + plotly 7.1.0, `--only-binary :all:`):
  `$SB/envs/compile_memo-new` (reflex 0.11.0a1 train, lucide 1.1.2a1), `$SB/envs/compile_memo-prev` (0.10.1, lucide 1.1.1).
- App `cm/` (one rich app, pages `/ /loop /loopmemo /refs /upload /plotly /recharts /editor /dyn /comps /rowfocus`).
  The same source runs on 0.10.1 (`NEW = hasattr(rx, "client_state")` guards the new-only APIs).
- Scripts: `scripts/srv.sh` (start/stop server in own process group), `scripts/cell.sh` (one matrix cell:
  compile/export/prod/dev with `REFLEX_AUTO_MEMOIZE` / `REFLEX_REACT_COMPILER`), `scripts/drive_cm.py` (Playwright,
  every page, JSON out), `scripts/summ.py` (summary). Rerun a cell:
  `scripts/cell.sh new_FT compile_memo-new $SB/apps/compile_memo/cm false true "compile export prod dev"`.

## Matrix (prod, Chromium) — n_probe / static_probe render counts: initial -> after 3x inc -> after 2x unrelated bump
| cell (auto_memoize, react_compiler) | py compile | export wall | js bytes | n_probe | static_probe | notes |
|---|---|---|---|---|---|---|
| prev 0.10.1 T,F | 0.62s | 13.5s | 7,787,087 | 3/6/8 | 1/1/1 | baseline |
| prev 0.10.1 T,T | 0.91s | 15.8s | 7,788,756 | | | export only |
| new T,F (default) | 0.61s | 11.5s | 7,789,729 | 3/6/8 | 1/1/1 | same as prev |
| new F,T | 0.65s | 20.3s | 7,843,670 | 1/4/4 | 1/1/1 | best render counts; compiler warning logged once |
| new T,T | 1.66s* | 19.7s (103s first run under load avg 7 — not reproducible) | 7,856,588 | 3/6/8 | 1/1/1 | |
| new F,F | — | 22.8s | 7,781,137 | 3/6/8 | 3/6/8 | warning logged ("disables page memoization"); whole page re-renders as warned |
(*single run under load.) memo_* probes (3 instances of one `@rx.memo` with event props) rendered once in every cell.
All cells: memo event handlers, cond on_mount/on_unmount branch order (`mA,page,uA,mB,uB,mA`), ComponentState
independence, client_state named+unnamed (`shared 1`, `A: 2, B: 0`), upload callbacks — correct.

## FINDING R1 (HIGH, regression): page code that references `refs` throws `ReferenceError: refs is not defined`
#7694 replaced the ref hook `const ref_x = useRef(null); refs['ref_x'] = ref_x;` with `useRegisteredRef("ref_x")`, so a page
(or the module a component lands in) no longer gets `import {refs} from "$/utils/state"` just because it holds a component
with an `id`. Any user/third-party JS emitted into the page that reads `refs[...]` now fails:
- `rx.Var("() => { refs['ref_target'].current.value = ... }").to(rx.vars.FunctionVar)` as an event handler — no-op + pageerror;
- `rx.call_function(rx.Var("() => refs['ref_target'].current.value"), callback=...)` — callback never fires;
- a custom component's `add_hooks` / `add_custom_code` reading `refs[...]` — page crashes into the error boundary.
Same breakage as reflex-enterprise AG Grid (enterprise cluster). `rx.set_focus/set_value/scroll_to`, `rx.call_script`
(evaluated inside state.js), forms with id'd fields and toasts are NOT affected (they resolve refs in state.js or carry the import).
Whether it bites depends on which module the code lands in: in the rich `cm` app with auto_memoize=True the raw-Var
handler worked by accident because its memo wrapper shared `app_components/cm/cm.jsx` with a form that imports `refs`.
Repro: `refsrepro/` app + `scripts/drive_refs.py`:
```
scripts/srv.sh start r compile_memo-new prod $SB/apps/compile_memo/refsrepro 3300 3300
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_refs.py http://localhost:3300 shot.png
scripts/srv.sh stop r
```
| | raw Var handler | call_function | add_hooks page |
|---|---|---|---|
| 0.10.1 dev/prod | `set by raw var` | `log: typed` | renders, `set by hook` |
| 0.11.0a1 dev/prod, auto_memoize T/F, compiler F/T | `''` + `refs is not defined` | `log:` | error boundary `ReferenceError: refs is not defined` |
Compiled evidence: `[refs]._index.jsx` imports `{useRegisteredRef}` only (0.10.1: `import {refs} from "$/utils/state"`).
Screenshots: `evidence/refs_*_prod.png`.

## Per-feature results (new = 0.11.0a1, prev = 0.10.1; both dev and prod unless noted)
- **#7793 foreach hooks** (`/loop`): on_mount/on_unmount with the loop var, add_hooks reading a loop-var prop (HookItem),
  nested foreach reading outer+inner var, index var, foreach over a dict — all run once per item in all 4 cells, prod:
  initial `alpha,alpha-x,alpha-y,idx0,beta,...,kv-one,kv-two`, add -> only `item3*` mounts, remove-first -> only
  `unmount alpha` / `hu:alpha`, reverse -> nothing remounts (keyed), remove-middle -> only gamma. Dev shows React
  StrictMode double mount (`m,u,m`) — expected. **prev: the page crashes** (`item_rx_state_ is not defined`,
  `kv_rx_state_ is not defined`) -> FIXED.
- **foreach inside `@rx.memo`** (`/loopmemo`, documented gap): page crashes into the error boundary with
  `ReferenceError: it_rx_state_ is not defined` in every cell, dev and prod; identical crash on 0.10.1. Not a regression;
  the changelog's "not covered yet" undersells it — it is a whole-page crash, not wrong counts.
- **#7409 uploads from callbacks** (`/upload`): backend-yielded toast action upload (with on_upload_progress), frontend
  toast action upload where the selection is changed AFTER the toast is shown (uploads the NEW selection
  `new1.txt,new2.txt`), frontend `rx.call_script(callback=upload)`, backend-yielded `call_script` callback upload — all work
  in new; prev: all four upload nothing + `filesById is not defined` pageerror -> FIXED (CMP-34 fixed).
- **#7721 streamed upload updates**: handler yielding 8 updates after a 20 MB upload: samples monotonic, final `7`,
  second run appends cleanly — same on prev (no stale restore seen on either).
- **CMP-01 hostile filenames** (`scripts/hostile_upload.py`, raw multipart to `/_upload` with `../../x`, `..\\..\\x`,
  `/etc/x`, `C:\\x`, `...`, `..`, `. .`, `sub/../../x`, unicode, RTL override, `%2e%2e%2f`, `nul`, `.hidden`, 300-char):
  everything lands inside `uploaded_files/` (`..`/`...`/`. .` -> `upload`, `sub/../../evil5` -> `sub/evil5.txt`) on new and
  prev -> still FIXED. The 300-char name makes the user handler raise `OSError: File name too long`; new: response is
  cut mid-stream (`incomplete chunked read`) + exception logged twice (event processor and granian "Application callable
  raised"); prev: HTTP 500 + same double log. Context only.
- **#7564/#7707/#7691 reproducible builds** (`repro/`): `reflex export --frontend-only` twice with PYTHONHASHSEED 1/2 and a
  third copy in another directory (seed 77): all 3937 files byte-identical (also with auto_memoize=False+react_compiler).
  prev: 178 differing files. Zip archives themselves differ (entry mtimes) — files identical. FIXED (CMP-27 memo
  module names now stable too). f-string ids: new `ref_fin_reflex___state____state__cm___cm___s_suffix_rx_state_`,
  prev `ref_fin__reflex_Var_4859621978695425598_...`.
- **f-string ids in foreach** (`/rowfocus`): `rx.set_focus(f"rf_{item}")` / `rx.set_value(...)` from any row always target
  the LAST row (all rows register the same ref `ref_rf_item_rx_state_`); identical on prev. Pre-existing, context.
- **#7276 lazy libs** (`CM_BUNDLE=1` adds `bundle_library(icon banana/info, recharts bar_chart)`;
  `scripts/lazy_probe.py`): lazy=false: every page incl. `/` and `/plotly` loads the recharts chunk `es6-*.js` + banana +
  info (~2.1 MB JS); lazy=true: `/` 1.59 MB, no recharts/banana/info; clicking the dynamic icon loads only `banana-*.js`,
  the dynamic callout only `info-*.js`, the dynamic chart only `es6-*.js`. Plotly page never loads recharts with lazy=true.
  Same totals on prev. `/recharts` with lazy=true is ~70 KB heavier than lazy=false (CMP-35, filed, unchanged).
  Dynamic recharts `bar_chart` renders an empty box on both versions (no error) — context.
  Without `bundle_library`, dynamic icons/charts fall back to the jsdelivr CDN (blocked here) on both versions.
- **CMP-05** module-scope `bundle_library()` survives compile: dynamic icon/callout render from the bundle in prod -> fixed.
- **Docs pattern: per-row `rx.client_state` in an `@rx.memo` row inside `rx.foreach`** (`/rows`, `scripts/drive_rows.py`,
  new only — API is new): toggling row "beta" opens only beta (good), but `rx.foreach` keys rows by INDEX, so after
  `remove first` the open state jumps to the row that moved into beta's slot (`[beta, alpha]` -> `open-alpha`). Same in
  T,F and F,T. Also the hidden `rx.cond` branch's on_mount fires for every row at mount (`open-alpha,open-beta,open-gamma`
  while none is open) — see next item.
- **on_mount inside `rx.cond` inside an `@rx.memo` body** (`/memocond`, `scripts/drive_mc.py`): the hidden branch's
  on_mount fires at mount (`mount-shown-x,mount-shown-y` with only x shown) and toggling fires nothing; compiled
  MemoRow shows the cond child's `useEffect` hoisted unconditionally into the memo function body. Identical on 0.10.1
  (pre-existing), but #7694's changelog promise "on_mount and on_unmount still follow their rx.cond branch" only holds
  outside `@rx.memo`.
- **on_unmount payload in an unkeyed foreach** (`/loopnokey`): items `[alpha,beta,gamma]`, `remove first` -> the backend
  receives `record_unmount("gamma")` while `alpha` was removed and gamma is still on screen (index keys + mount-time
  closure with `[]` deps). New behaviour (0.10.1 crashes on this page). #7793 "each item now runs its own hooks" — the
  hooks run per position, not per item. With an explicit `key=item` (`/loop`) the payloads are correct.
- **Python compile time, large app** (`big/`: 40 pages x 150 stateful blocks, `reflex compile`, 2 runs each):
  new T,F 18.3-21.6 s; new F,T 8.4-8.8 s (2.2x faster, claim holds); new T,T 18.2-18.5 s; prev T,F 17.1-20.0 s.
  `.web/app_components` 265 KB -> 3 KB with auto_memoize=False.
- **Controlled inputs under every cell** (`/typing`, `scripts/drive_typing.py`, dev+prod, T,F / F,T / F,F): fast typing
  into plain, debounced, cond-wrapped and text_area controlled inputs — no lost characters, state matches.
- **Warnings**: `react_compiler=True is experimental...` logged once per process (good). `auto_memoize=False without
  react_compiler=True disables page memoization...` is NOT deduplicated: 2x per `reflex compile`, 5x per `reflex run`
  (dev) — low noise.
- **In-place upgrade of a react_compiler app** (`cm_upg`: `.web` built by 0.10.1 with react_compiler, then 0.11.0a1):
  package.json `babel-plugin-react-compiler` 1.0.0 -> `0.0.0-experimental-a1856f3-20260507`, export + prod run clean.
  Leftover `.web/reflex.json` stays (harmless).
- **#7716 callout icon**: component icon, `rx.cond` of icons (switches check<->x), `rx.match` of icons (info ->
  triangle_alert -> circle_x), ComponentVar via `@rx.memo` arg, Var icon name — all render in dev+prod, all cells.
  0.10.1: `TypeError: Icon name must be a string` at compile (expected — new feature).
- **#7753** `rx.code_block(language="text", show_line_numbers=True, can_copy=True)` renders plain text with line numbers;
  Var language `"text"` too. 0.10.1 rejects `"text"` at compile (`Invalid var passed for prop CodeBlock.language`).
- **#7750 typing** (`typing/typ.py`, pyright 1.1.414 from `events_await-typing-*` venvs, read-only): new: component-first
  match -> `Component`, str-first -> `Var[Unknown]`; prev: `Component | Var[Unknown]` everywhere + callout icon component
  rejected. Fixed. (Minor: str match types as `Var[Unknown]`, not `Var[str]`.)
- **#7747 input clear_events**: only in reflex-components-internal, which was NOT released in this train (PyPI latest
  0.0.34; the change is an unreleased news fragment). Radix `rx.input(clear_events=...)` does not exist (it is turned
  into a style prop and fails: `EventHandler cannot be used as style values`). Skipped.
- **#7674 lucide digit icons** (`/comps`): with lucide 1.1.2a1 Var-tag `grid_2x_2`, `grid_3x_3` render (also in
  `rx.foreach` and `rx.callout(icon=Var)`). **With lucide 1.1.1 + reflex 0.11.0a1** (`$SB/envs/compile_memo-l111`,
  what `pip install -U reflex` gives, floor `reflex-components-lucide>=1.1.1`): grid_2x_2 / grid_3x_3 blank +
  `[lucide-react]: Name in Lucide DynamicIcon not found` x11 — fix does not reach upgraders. Unknown names
  (`no_such_icon_x`) via Var keep showing the previous icon + console error on both versions (pre-existing).
- **#7057 mapping inference** (`py/mapping_perf.py`): 2M-entry dict: 0.1 ms new vs 62 ms prev; a heterogeneous value past
  the 100-entry sample is ignored on both (`Mapping[str, int]`) — by design.
- **Blocking-monitor false positive (adjacent, #7672)**: the first event whose handler takes a `dict` arg
  (`on_upload_progress`) lazily runs `from reflex.model import Model` (imports sqlalchemy, 0.2-0.9 s) inside
  `_transform_event_arg`; dev then warns `Event handler S.on_progress is blocking the event loop` with a stack through
  sqlalchemy imports — blames the user's trivial handler for reflex's own lazy import. Lazy import exists in 0.10.1 too;
  the warning is new.
- **enterprise refs survey** (context for the enterprise cluster): `reflex_enterprise/components/map/base.py` carries
  `refs_var_data` (safe); `auth/oidc/state.py` uses `refs[...]` inside `rx.call_script` (safe, state.js scope);
  `ag_grid/aggrid.py:253,902` emit bare `refs[...]` (the known break).
