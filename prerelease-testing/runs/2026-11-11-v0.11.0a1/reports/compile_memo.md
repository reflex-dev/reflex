CLUSTER: compile_memo
SUMMARY: The new compile/memo features mostly work end to end in Chromium, in dev and prod, across all four auto_memoize x react_compiler cells. Fixed and confirmed: foreach hooks (#7793), uploads started from toasts and call_script (#7409), reproducible exports (#7564/#7707/#7691), per-component lazy libs (#7276), callout icon components, code_block "text", match typing and mapping inference perf. auto_memoize=False + react_compiler=True gives the best render counts and compiles 2.2x faster in Python. There is one HIGH regression: the #7694 switch to `useRegisteredRef` stopped pages from importing `refs`, so any page-level JS that reads `refs[...]` throws `ReferenceError` (raw Var handlers, `rx.call_function` with a JS function Var, custom components' `add_hooks`/`add_custom_code`, and the AG Grid break seen in enterprise). Several medium issues are not regressions; they cover foreach/memo lifecycle semantics and the lucide fix not reaching in-place upgraders.
ARTIFACTS: /home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/compile_memo/
TESTS:
- [pass] matrix auto_memoize x react_compiler (prod+dev; cm app, 12 pages): every cell gave correct State, @rx.memo event props (3 instances), rx.cond on_mount/on_unmount branch order, ComponentState isolation, named+unnamed client_state, uploads and controlled typing. Render probe n/static (initial/after 3 inc/after 2 unrelated): prev T,F 3/6/8 and 1/1/1; new T,F same; new F,T 1/4/4 and 1/1/1 (the compiler skips unrelated re-renders); new T,T 3/6/8 and 1/1/1; new F,F static re-renders on every change, as the warning says.
- [pass] compile time: on a large app (40 pages x 150 blocks) Python compile takes 18.3 s (T,F), 8.4 s (F,T), 18.2 s (T,T); prev takes 17.1 s. A vite export of cm takes 11.5 s (T,F) vs about 20 s with the compiler. JS bytes rise by +54 to +67 KB with the compiler.
- [anomaly] the warning "auto_memoize=False without react_compiler=True..." is logged 2x per `reflex compile` and 5x per dev `reflex run` because it is not deduplicated. The react_compiler warning is logged once, which is correct.
- [fail] the refs surface: `rx.Var("() => refs[...]").to(FunctionVar)` handler, `rx.call_function(Var("() => refs[...]"))` and custom `add_hooks` reading `refs[...]` all break on new (dev+prod, every cell); they work on 0.10.1. `rx.set_focus/set_value/scroll_to`, `rx.call_script` with refs, forms with id'd fields and toasts still work. Among published reflex-components-* wheels, only sonner emits `refs[`, and it carries its own import.
- [pass] #7793 foreach hooks: on_mount/on_unmount using the loop var, add_hooks reading a loop-var prop, nested foreach (outer+inner var), index var and dict foreach all fire once per item. Add, remove-first, remove-middle and reverse fire exactly the expected per-item events with key=item. 0.10.1 crashes on the same page.
- [anomaly] foreach inside @rx.memo (documented gap): the whole page crashes into the error boundary (`it_rx_state_ is not defined`) in every cell and in prod. 0.10.1 crashes the same way. The changelog's "not covered yet" undersells a page crash.
- [fail] the unkeyed foreach on_unmount payload names the wrong item: removing the first of [alpha,beta,gamma] sends `record_unmount("gamma")`. New behaviour, since 0.10.1 crashes here.
- [fail] the docs pattern "per-row client_state via @rx.memo row in foreach": state is tied to the row's position, not the item, so after remove-first the open row jumps to its neighbour. The hidden rx.cond branch's on_mount also fires for every row.
- [anomaly] on_mount inside rx.cond inside an @rx.memo body fires at mount even when hidden, and toggling fires nothing. The same happens on 0.10.1. #7694's claim that on_mount "follows its rx.cond branch" only holds outside memo.
- [pass] #7409 uploads: backend toast action upload with progress, frontend toast action where the selection changed after the toast appeared (uploads the new selection), frontend call_script callback and backend call_script callback all work. 0.10.1 uploads nothing and throws `filesById is not defined`.
- [pass] #7721: a handler yielding 8 updates after a 20 MB upload gives a monotonic final value; behaviour is the same on prev, and no stale restore was seen.
- [pass] #7564/#7707/#7691: two exports with PYTHONHASHSEED=1 and 2, plus a copy in another directory with seed 77, produce 3937 byte-identical files, also in F,T. Prev differs in 178 files. Zip archive bytes still differ (entry mtimes).
- [anomaly] an f-string id in foreach (`rx.set_focus(f"rf_{item}")`) always targets the last row, because every row shares the ref `ref_rf_item_rx_state_`. Same on 0.10.1.
- [pass] #7276 lazy libs with bundle_library (icon banana/info, recharts): with lazy=true the `/` and plotly pages no longer load the recharts, banana or info chunks (about 525 KB less JS); each dynamic component loads only its own chunk. With lazy=false, recharts loads on every page, as on prev.
- [anomaly] a dynamic `rx.recharts.bar_chart` (state var component) renders an empty box with no error on both versions. Without bundle_library, dynamic icons and charts fall back to the jsdelivr CDN on both versions.
- [pass] CMP-01: hostile multipart names (`../../x`, `..\\..\\x`, `/etc/x`, `C:\\x`, `...`, `..`, `. .`, `sub/../../x`, unicode, RTL override, `%2e%2e%2f`, `nul`) all stay inside uploaded_files/, on new and prev.
- [anomaly] when an upload handler raises (OSError on a 300-char name), new cuts the streamed response mid-body (`incomplete chunked read`) and logs the exception twice. Prev returns HTTP 500 and also logs twice.
- [pass] #7716 callout icon: component icon, rx.cond of icons, rx.match of icons, an icon passed into an @rx.memo as a ComponentVar, and a Var icon name all render and switch, in dev and prod.
- [pass] #7753: `code_block(language="text")`, also with a Var language, line numbers and copy, renders. 0.10.1 rejects it at compile time.
- [pass] #7750: pyright types component-first match as `Component` and str-first as `Var[Unknown]`. Prev gives `Component | Var` and rejects callout icon components.
- [pass] #7674 with lucide 1.1.2a1: Var-tag `grid_2x_2`/`grid_3x_3` render in foreach, standalone and in callout.
- [fail] #7674 with lucide 1.1.1, which `pip install -U reflex` keeps: grid icons stay blank and log `DynamicIcon not found` x11.
- [skipped] #7747 clear_events: the change lives only in reflex-components-internal, which was not released in this train (PyPI 0.0.34). Radix rx.input has no clear_events.
- [pass] #7057: figure_out_type on a 2M-entry dict takes 0.1 ms (prev 62 ms).
- [pass] in-place upgrade of a react_compiler app from a 0.10.1-built .web: the babel plugin moves 1.0.0 -> 0.0.0-experimental-a1856f3-20260507, and export plus prod are clean.
- [pass] fast typing into controlled, debounced, cond-wrapped and text_area inputs works in T,F / F,T / F,F, dev and prod.
- [anomaly] blocking monitor false positive: the first dict-arg event lazily imports sqlalchemy (`from reflex.model import Model` in `_transform_event_arg`, 0.2-0.9 s). The dev warning blames the user's handler (`S.on_progress is blocking the event loop`).
REVERIFIED:
- CMP-24: fixed — a hook component in rx.foreach (on_mount and add_hooks with the loop var) renders and fires per item; 0.10.1 still crashes.
- CMP-34: fixed — rx.upload_files() from toast actions and call_script callbacks works on 0.11.0a1; 0.10.1 still throws `filesById is not defined`.
- CMP-27: fixed — memo module names and all 3937 export files are identical across hash seeds and paths.
- CMP-01: fixed — raw multipart hostile names stay inside the upload dir (new and prev).
- CMP-05: fixed — module-scope bundle_library() survives a prod compile; dynamic icon and callout render from the bundle with lazy off and on.
- HYD-15: changed (partial) — dynamic components referencing bundled libs serialize and render in single-port prod granian workers; `--backend-only` workers were not tested.
- CMP-35: still-broken — on a page that uses recharts directly, lazy=true is about 70 KB heavier than lazy=false (on `/` it saves about 525 KB).
- R101-08: changed — react_compiler=True now logs that the compiler silently skips components it cannot compile; bailouts were not counted.
ISSUES:
- TITLE: Page code that reads `refs[...]` throws `ReferenceError: refs is not defined` (useRegisteredRef no longer imports refs)
  SEVERITY: high
  REGRESSION: yes
  REPRO: Use app `compile_memo/refsrepro/` (one input id="target" plus three probes: a raw `rx.Var("() => { refs['ref_target'].current.value = 'x' }").to(rx.vars.FunctionVar)` on_click, `rx.call_function(rx.Var("() => refs['ref_target'].current.value"), callback=S.set_log)`, and a Fragment subclass whose `add_hooks` returns `"useEffect(() => { refs['ref_target'].current.value = 'set by hook'; }, [])"`). Run `scripts/srv.sh start r compile_memo-new prod $SB/apps/compile_memo/refsrepro 3300 3300`, then `NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/drive_refs.py http://localhost:3300 shot.png`. On 0.10.1 (venv compile_memo-prev), dev and prod: the raw handler sets the value, call_function logs "typed", and the hook page renders "set by hook". On 0.11.0a1, in dev and prod with auto_memoize T or F and react_compiler F or T: the raw handler is a no-op with pageerror `refs is not defined`, call_function never calls back, and /hook shows the error boundary.
  EVIDENCE: The compiled `.web/app/routes/[refs]._index.jsx` imports only `{useRegisteredRef}` from "$/utils/state"; 0.10.1 imports `{refs}`. Console: `ReferenceError: refs is not defined at .../assets/_hook_._index-*.js`. Screenshots: evidence/refs_new_truefalse_prod.png vs evidence/refs_prev_truefalse_prod.png. In a large app it can pass by accident when a memo wrapper shares a module with a form that imports refs (cm /refs in T,F). The same root cause produces enterprise's AG Grid `refs` break; reflex_enterprise map/oidc are safe.
- TITLE: on_unmount/on_mount payloads in an unkeyed rx.foreach name the item that was mounted at that position, not the item removed
  SEVERITY: medium
  REGRESSION: no (0.10.1 crashes on this page; the behaviour is new with #7793)
  REPRO: cm app page /loopnokey: `rx.foreach(S.items, lambda item: rx.text(item, on_mount=S.record_mount(item), on_unmount=S.record_unmount(item)))` with items ["alpha","beta","gamma"]. Click "remove first" (pops index 0). Run `scripts/drive_mc.py http://localhost:3300` against a prod server of cm.
  EVIDENCE: `nk_after_remove_first: items [beta, gamma], unmounted: gamma`. rx.foreach keys children by index (`key:index_...`), and the generated useEffect captures the loop var with `[]` deps. Giving the row `key=item` (/loop) yields the correct payloads, but the docs never say a key is needed.
- TITLE: Per-row `rx.client_state` in an @rx.memo row inside rx.foreach (docs pattern) follows the row position, so state jumps rows after a removal
  SEVERITY: medium
  REGRESSION: no (new API, #6936)
  REPRO: cm app page /rows: the docs' `@rx.memo def memo_row(item)` with `expanded = rx.client_state(False)` and `rx.foreach(S.items, lambda item: memo_row(item=item))`. Open row "beta", click "reverse", then "remove first". Run `scripts/drive_rows.py http://localhost:3300` (prod, T,F and F,T).
  EVIDENCE: after remove-first `names [beta, alpha], open [open-alpha]`, i.e. the open state moved from beta to alpha. Root cause is the index-keyed foreach plus the withClientStateScope instance. At initial mount, `mounted: ...open-alpha,...open-beta,...open-gamma` even though no row was open (next issue).
- TITLE: on_mount/on_unmount of a component inside rx.cond inside an @rx.memo body fire unconditionally (hoisted into the memo function)
  SEVERITY: medium
  REGRESSION: no (identical on 0.10.1)
  REPRO: cm app page /memocond: `@rx.memo def memo_cond(show: rx.Var[bool], label)` containing `rx.cond(show, rx.text(..., on_mount=S.log_branch("mount-shown-"+label), on_unmount=...))`, used as `memo_cond(show=S.flag, label="x")` and `memo_cond(show=~S.flag, label="y")`. Load the page, then toggle. Run `scripts/drive_mc.py`.
  EVIDENCE: initial `shown [shown-x]` but `branch: mount-shown-x,mount-shown-y`; after toggling, nothing new fires. The compiled MemoRow/MemoCond body has the cond child's `useEffect(..., [])` at top level. #7694's changelog says on_mount "still follow their rx.cond branch", which is true only outside @rx.memo.
- TITLE: rx.foreach inside an @rx.memo function with item hooks crashes the whole page (documented gap)
  SEVERITY: medium
  REGRESSION: no (same crash on 0.10.1)
  REPRO: cm app page /loopmemo: `@rx.memo def memo_loop(items: rx.Var[list[str]])` returning `rx.foreach(items, lambda it: rx.text(it, on_mount=S.record_mount("ml-"+it)))`. Open /loopmemo in any cell, dev or prod.
  EVIDENCE: error boundary with `ReferenceError: it_rx_state_ is not defined` (evidence/loopmemo_crash_new_TF_prod.png). The changelog says only "not covered yet"; the outcome is a page crash, not wrong counts.
- TITLE: #7674 lucide digit-icon fix does not reach in-place upgraders (reflex 0.11.0a1 requires reflex-components-lucide>=1.1.1)
  SEVERITY: medium
  REGRESSION: no (the icons were blank before too; the advertised fix is missing)
  REPRO: Build a venv from `reqs/new_l111.txt` (reflex 0.11.0a1 train + lucide 1.1.1). On cm page /comps, `rx.icon(S.icon_name)` with icon_name="grid_2x_2" and the same in rx.foreach. Run `scripts/cell.sh l111_TF compile_memo-l111 $SB/apps/compile_memo/cm true false prod comps`.
  EVIDENCE: `grid_2x_2 => NO-SVG, grid_3x_3 => NO-SVG` plus `[lucide-react]: Name in Lucide DynamicIcon not found` x11; with 1.1.2a1 both render (evidence/comps_lucide111.png vs comps_lucide112a1.png).
- TITLE: rx.set_focus / rx.set_value with an f-string id inside rx.foreach always target the last row
  SEVERITY: low
  REGRESSION: no (same on 0.10.1)
  REPRO: cm page /rowfocus: `rx.foreach(S.items, lambda item: rx.hstack(rx.input(id=f"rf_{item}"), rx.button("f", on_click=rx.set_focus(f"rf_{item}"))))`. Click each "f" button.
  EVIDENCE: `focus_btn_i_focuses: [2, 2, 2]`, and set_value sets only the last input. All rows register `useRegisteredRef("ref_rf_item_rx_state_")` while the DOM ids are distinct.
- TITLE: Dev blocking-monitor warning blames a trivial user handler for reflex's lazy sqlalchemy import on the first dict-arg event
  SEVERITY: low
  REGRESSION: unknown (the lazy import exists in 0.10.1; the warning is new in #7672)
  REPRO: cm dev server, /upload: select a file and click "upload direct" (handler `on_progress(self, prog: dict)` only appends a string).
  EVIDENCE: `Warning: Event handler S.on_progress is blocking the event loop (threshold: 0.200s)`, with the stack running through `_transform_event_arg -> from reflex.model import Model -> import sqlalchemy` (0.2-0.9 s). See logs/new_dev_T_F.log lines 66-140 in $SB.
- TITLE: "auto_memoize=False without react_compiler=True" warning repeats (2x per compile, 5x per dev run)
  SEVERITY: low
  REGRESSION: no (new warning)
  REPRO: `REFLEX_AUTO_MEMOIZE=false REFLEX_REACT_COMPILER=false reflex compile` (or `reflex run`) in cm.
  EVIDENCE: logs new_FF_compile.log (2 occurrences) and new_FF_dev.log (5). The react_compiler warning is deduplicated by `_warned_react_compiler`; this one has no such guard.
NOT_COVERED: HYD-15 on `--backend-only` workers; R101-01 (memo staleness after a component mutates state objects); R101-02 (fork preload threads, CLI/server area); counting React Compiler bailouts (R101-08); upload + middleware (#7782; owned by events_await); Windows; dev HMR edits under react_compiler; a redis state manager under the matrix. The chromium driver had no internet, so CDN fallbacks for unbundled dynamic libraries could not succeed; that is environmental and the same on both versions.
