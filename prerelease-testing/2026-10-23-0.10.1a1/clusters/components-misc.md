# Cluster `components-misc` — moment, data_editor, shiki/code, lucide, radix misc

## Changelog lines (verbatim)
- (reflex #7591 / reflex-components-moment #7591) Expose `rx.moment_provider` for sharing locale, timezone, formatting, and timer defaults across Moment components. Expose the `utc`, `calendar`, `from_`, `to`, `ago`, `element`, `fallback`, `filters`, and `renderers` options of `react-moment` 2.x, which previously rendered as CSS.
- (reflex-components-dataeditor #7607) `rx.data_editor` columns backed by state now get the same defaults as literal columns: `type` defaults to `"str"`, `id` to the lowercased `title`, and a column may be given as just its title string. The column dicts passed to `columns` are no longer modified in place. Faster redraws for grids whose `columns` or `data` come from state.
- (reflex-components-code #7437) Fix `use_transformers=True` on the Shiki code block rendering no transformers: the default shikijs transformers and their styles are now applied again.
- (reflex-components-lucide #7604) Preserve imports required by icon props and expose the correct Lucide module through `import_var`.
- (reflex-components-radix #7098) Avoid Emotion's unsafe `:first-child` SSR warning for Radix Accordion items in development mode.
- (reflex-components-radix #7431) Forward progress values to the Radix Root so its state and ARIA attributes reflect the displayed progress.
- (reflex-components-radix #7555) Remove the `as_child` prop from `rx.radio_cards.root` and `rx.radio_cards.item`.

## What to build
One page per component. Moment: `rx.moment_provider(locale=..., timezone=..., interval=...)` wrapping several `rx.moment` with `utc=True`, `calendar`, `from_`/`to`/`ago`, `element="span"`, `fallback`, `filters`, `renderers`, props bound to state and to `client_state`; verify rendered text AND that none of those props leak into a `style` attribute or CSS (inspect DOM); live tick with `interval`. data_editor: columns from a state var as title strings and as partial dicts (no type/id), data from state; mutate the columns var after mount; check the python dict is not mutated (assert `columns == original` in a handler); edit cells and verify `on_cell_edited`; measure redraw with a 2000-row grid vs 0.10.0. Shiki `rx.code_block` (`rx._x.code_block`/`rx.code_block.shiki`?) with `use_transformers=True` — look at the released source for the exact API — confirm transformer classes/styles appear in DOM (diff notation, highlight lines). Lucide: `rx.icon("home")`, icon props such as `rx.input(icon=...)`/`rx.badge` or any component taking an icon as prop, icons inside `rx.foreach` with a dynamic name var, and `rx.icon` inside `@rx.memo`; check generated imports in `.web` and the browser for missing-import errors. Accordion in dev: console must not show the Emotion `:first-child` warning. Progress: `rx.progress(value=State.v)` → check `aria-valuenow`/`data-state`. `rx.radio_cards.root(as_child=True)` → confirm it is now a clear error at compile time (or TypeError) rather than a silent crash.

## Combine it with
- Each component under `rx.cond` and `rx.foreach`, in prod mode too.
- 0.10.0 baseline for every visual difference.
