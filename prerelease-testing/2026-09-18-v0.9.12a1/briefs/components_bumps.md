# Cluster `components_bumps` — the component-library alphas: recharts 0.9.4a1 (#6708 sankey + `use_chart_width`, #6833 prop routing), dataeditor 0.9.3a1 (#7081 image cells), plotly 0.9.7a1 (#6977 `divId`), sonner 0.9.4a1 (#7157), code 0.9.6a1 (#7078 copy button), core 0.9.10a1 (#7124 datadisplay namespace, #7078 badge a11y, #6860 upload 400), radix 0.9.10a1, markdown 0.9.4a1, gridjs 0.9.2a1 (`CommonTag` `_render`), reflex-base `use_hook_var`/`use_id` (#6708)

Changelog lines (verbatim):
- (recharts) Added a Recharts Sankey chart wrapper (`rx.recharts.sankey_chart`) with support for custom node and link renderers, and `rx.recharts.use_chart_width()` for reading the rendered chart width as a `Var`. (#6708)
- (recharts) Fix Recharts component props (e.g. `stroke_dasharray` on `reference_line`, `tick_formatter` on `x_axis`/`y_axis`) being misclassified as CSS and routed to `wrapperStyle` instead of reaching the underlying Recharts component. (#6833)
- (reflex-base) Add `rx.vars.use_hook_var()` to create a `Var` bound to the value of a no-argument React hook imported from a given library, and `rx.vars.use_id()` to get React's stable `useId` value for the rendered component. (#6708)
- (reflex-base) Add native image cells to `rx.data_editor` with `type="image"`, allowing image thumbnails and text to appear together in the same grid. (#7081) / (dataeditor) Ensure `rx.data_editor` image previews include Glide Data Grid's required carousel styles. (#7081)
- (plotly) `rx.plotly(..., id="...")` now reaches the DOM: the `id` prop is rendered as react-plotly.js's `divId`. (#6977)
- (sonner) Fix `rx.toast` `action` and `cancel` buttons not triggering their `on_click` events when the toast is fired from a frontend event trigger. (#7157)
- (code) Give default code-copy buttons an accessible name and prevent them from submitting an enclosing form. (#7078)
- (core) `reflex_components_core.datadisplay` no longer advertises `code_block`, `data_editor` and friends: those moved to the standalone packages, so accessing them here raised `ModuleNotFoundError`. Reach them as before via `rx.code_block` / `rx.data_editor`, or `reflex.components.datadisplay.code`. (#7124)
- (core) Give the Built with Reflex badge an accessible name when its visual text is hidden on small screens. (#7078)
- (core) Return a controlled 400 response when an upload request references an unknown event handler. (#6860)
- (core, radix, markdown, gridjs) Annotate `_render` overrides as returning `CommonTag`, the new base of every tag class. (#7121)
- (radix) The segmented control no longer keeps a permanent reference to the vars it builds its selected-index expression from. (#7198)

Read #6708 (the sankey docs page in `docs/` on the release branch shows the intended API for
custom node renderers, `use_chart_width`, `use_hook_var`, `use_id`), #6833, #7081, #6977.

## Build a component gallery (dev AND prod; baseline the bug fixes on 0.9.11.post1)

- Sankey: static data; State-driven nodes/links that change on a button; custom node and link
  renderers (per the docs) ; `use_chart_width()` shown in `rx.text` and used in an `rx.cond`;
  the chart inside `rx.foreach` (two charts from a list) and inside an `@rx.memo`. Resize the
  viewport and check the width var updates.
- Recharts props: `rx.recharts.reference_line(stroke_dasharray="3 3")`, `x_axis(tick_formatter=...)`,
  `y_axis(tick_formatter=...)`, `line(stroke_dasharray=...)`, `cartesian_grid(stroke_dasharray)`:
  inspect the SVG (`stroke-dasharray` attribute present; the tick labels formatted) and the
  wrapper div's `style` (must NOT contain them). Baseline.
- `rx.data_editor` with columns `[{"title":"pic","type":"image"},{"title":"name","type":"str"}]`
  and rows whose image cell is a list of local asset URLs; State-driven rows; click/double-click
  an image cell to open the preview overlay → screenshot; check the carousel styles are applied
  (no unstyled overlay, no 404 for a CSS file in the network log). In an `@rx.memo` too.
- `rx.plotly(fig, id="myplot")` → `document.getElementById("myplot")` exists; also inside
  `rx.foreach` with per-item ids; and `rx.plotly` with a State-var figure.
- Toasts (see also the event_loop cluster — here focus on component composition): fire
  `rx.toast.success/error/info` with `action`/`cancel` from frontend triggers inside `@rx.memo`,
  `ComponentState`, `rx.foreach` items; `rx.toast(...)` returned from a background task; toast
  `duration`, `position`, `close_button`; `rx.toast.dismiss`.
- `rx.code_block` INSIDE an `rx.form` with an `on_submit` counter: click the copy button → the
  counter must not increment and clipboard gets the code (Playwright `context.grant_permissions(["clipboard-read"])`);
  the copy button has an accessible name (`aria-label`/text); in prod the SSR HTML already
  contains the readable code (fetch the html without JS); code blocks far below the fold
  highlight when scrolled into view; change `language`/`theme` via State → still readable.
- `rx.markdown` with fenced code, tables, math, links, components map; `rx.data_table` (gridjs)
  with State data, sorting, search, pagination; `rx.segmented_control` bound to State (#7198).
- Namespace sanity in a script (venv guard!): `import reflex_components_core.datadisplay as dd; dir(dd)`;
  `from reflex.components.datadisplay import code, dataeditor`; `rx.code_block`, `rx.data_editor`,
  `rx.data_table`, `rx.logo`, `rx.recharts.sankey_chart`, `rx.vars.use_hook_var`, `rx.vars.use_id`
  all resolve; `reflex_components_core.datadisplay.code_block` → what error now?
- `use_id()` in `rx.foreach` items as `id=` and matching `html_for` on a label (unique per item,
  stable across re-render); `use_hook_var("useIsClient", "usehooks-ts")`-style hook (check the
  docs for the exact signature; pick a real no-arg hook from a small npm library) shown in
  `rx.text`, inside `rx.cond`, inside `@rx.memo`.
- Upload endpoint with an unknown handler name via `httpx` multipart → 400 with a message, not 500.
- Built-with-Reflex badge at a 360 px viewport: has an accessible name (`aria-label`).
