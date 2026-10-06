# Cluster `dataeditor_components` — reflex-components-dataeditor 0.9.3.post1 (published today) + component interaction sweep

Ports: frontend 3420-3439, backend 8420-8439. Work dir: $SB/apps/dataeditor_components/. DEST: /home/user/reflex/prerelease_testing/2026-10-06/dataeditor_components/

## Why this cluster exists
`reflex-components-dataeditor 0.9.3` was yanked (wrong `reflex-base` floor) and `0.9.3.post1` was published
on 2026-10-06 16:35 UTC — AFTER the previous campaign — with `reflex-base>=0.9.12`. Nobody has tested it.
Both `reflex==0.10.0a1` and the stable `reflex==0.9.12` now resolve to it (it is in `$SB/envs/alpha` and
`$SB/envs/stable`). Its changelog: "Ensure `rx.data_editor` image previews include Glide Data Grid's
required carousel styles. (#7081)" plus the post1 floor bump (#7439 on main). Also in this cluster, the
component-level changelog entries whose interaction surface the previous campaign's single dashboard
did not fully cover:
- (core) Fix `rx.match` raising `ReferenceError: Can't find variable` at render when a state Var is used only in a case condition with component branches. (#6675)
- (core) Exclude IDs on forms and other non-controls from form submissions while preserving unset ID-backed controls and supporting custom controls marked with `_is_form_control`. (#7227)
- (plotly) Normalize string Plotly layout titles to the `{"title": {"text": "..."}}` format required by Plotly.js. (#7226)
- (recharts) Allow Recharts axis tick formatters to use Reflex function vars. (#7366)
- (base) Auto-memoized `@rx.memo` wrapper names no longer repeat the wrapped memo component's tag. (#7004)
- (base) `rx.download(data=State.var)` percent-encodes the JSON it puts in the `data:` URL ... (#7325)
- (code) Update Shiki and its transformers to 4.5.0; (moment) Moment 2.31.0 ...; (radix) slider 1.4.7 / progress 1.1.16; (core) react-dropzone 17.0.0, react-error-boundary 6.1.6 (#7424)

## What to do
1. Data editor on BOTH `$SB/envs/alpha` (0.10.0a1) and `$SB/envs/stable` (0.9.12), dev and prod:
   `rx.data_editor` with columns of every type (text, int, float, bool, image, uri, markdown, bubble,
   drilldown, row-id), data from a State var; `on_cell_edited` → State; `on_cell_clicked`; image cells
   with real local images (`assets/`) and remote URLs — open the image preview overlay by clicking the
   cell and screenshot it: the carousel styles fix (#7081) must show a correctly styled overlay (no
   unstyled/overlapping images); `theme` prop; `get_cell_content` path with `rx.foreach`-built rows; the
   editor inside an `@rx.memo` component and inside a `ComponentState`; two editors on one page; a
   data editor whose rows come from `rx._x.client_state`-driven filter; column resize/sort if exposed;
   large data (5,000 rows) scroll performance (no console errors, no freeze). Check the console for
   Glide errors/warnings and the network tab for the carousel/overlay CSS actually loading.
   Also verify `pip show`/`uv pip show` metadata of 0.9.3.post1 and that `uv pip install
   'reflex-components-dataeditor==0.9.3.post1' 'reflex-base==0.9.11'` is REFUSED (floor works).
2. Form submissions (#7227) beyond the previous dashboard: a form containing a `rx.data_editor`, a
   `rx.slider`, `rx.checkbox`/`rx.switch` with ids but no `name`, an `rx.upload` dropzone with an id, a
   nested `rx.form` in a dialog, a `ComponentState`-owned form; a custom component marked
   `_is_form_control`; submit and assert the exact payload dict (print it in the handler): no stray keys
   from non-controls, ID-backed controls present with empty values when unset. Compare the payload with 0.9.12.
3. `rx.match` (#6675) with the Var ONLY in a case condition, nested in `rx.foreach` over `ComponentState`
   instances and inside `rx.memo`, with component AND literal branches, in prod.
4. Memo wrapper naming (#7004): walk React fibers (`page.evaluate` over `__reactFiber$...` keys) and list
   `displayName`/type names of auto-memoized wrappers around a `@rx.memo` component used 3 times with
   different props and inside foreach; confirm no doubled tag names; compare to 0.9.12.
5. Plotly (#7226): string title, dict title, title bound to a State var that changes, `rx.plotly` inside
   `rx.cond` toggled on/off, two figures with the same layout object, `go.Figure` with `layout.title` set
   both ways; check Plotly console warnings.
6. Recharts (#7366): tick formatter as `rx.Var.create(...)` function var and as `rx.vars.function.FunctionStringVar`
   referencing a State var; inside `rx.memo`; chart data updated by a background task every 500ms for
   10s → no console errors, no leaked listeners (check `performance.memory` trend roughly).
7. Radix slider 1.4.7 / progress 1.1.16: keyboard interaction (arrow keys) on the slider bound to a State
   var with `on_change` + `on_value_commit`; progress bound to a State var updated by a background task;
   both inside `ComponentState`.
8. Shiki 4.5.0: `rx.code_block` with `theme`/`language` bound to State vars that change at runtime; a
   markdown block with fenced code; the known pre-existing `use_transformers=True` defect — just confirm
   it is unchanged, do not re-report. Moment 2.31: `rx.moment` with `tz`/`locale`/`format` from State; a
   value updated every second by `interval`; `duration` formatting.
9. `rx.download(data=State.var)` with a 2 MB string containing `#`, `%`, emoji, NUL-free binary-ish text;
   check the downloaded bytes match exactly (Playwright `expect_download`).
Baseline on `$SB/envs/stable` for every failure.
