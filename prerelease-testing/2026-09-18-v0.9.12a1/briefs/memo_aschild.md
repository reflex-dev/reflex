# Cluster `memo_aschild` — transparent auto-memo wrappers (#6850), memo app-wraps (#7176), svg memo (#6708), shared event chains (#7122), compile fast paths (#7121), form.message (#7133), error boundary (#7130)

Changelog lines (verbatim):
- Fix stateful inputs under `rx.form.control(..., as_child=True)` so they receive the parent form's attributes and their values appear in submitted form data. (#6850)
- (reflex-base) Automatically memoized components now preserve parent-provided props, event handlers, styles, and refs, allowing them to work correctly with Radix `as_child` wrappers. (#6850)
- (core) `rx.debounce_input` (which fully-controlled inputs compile to) now delivers a parent-provided ref to the underlying input element instead of the component instance, fixing crashes under `rx.form.control(..., as_child=True)`. (#6850)
- (plotly) Avoid redundant frontend dependency installation when using Plotly components. (#6850 — `mergician` is now a base dependency)
- Fix `@rx.memo` components dropping the app wraps their body requires. Providers requested by a nested child, or through var data as `rx.upload`'s `UploadFilesProvider` is, now reach the app root — so a provider-backed component behaves the same inside a memo as inlined into the page. (#7176)
- (core) `rx.el.svg` and its children now render as one memoized component, so `defs` such as gradients and the elements that reference them by id always share one render scope. (#6708)
- Share one event chain per handler and trigger across call sites, and reuse memoized event wrappers by chain identity during compilation. (#7122)
- Speed up compilation by reading only the props a component sets, caching literal Var dispatch by value type, and trimming render and app-wrap bookkeeping. Tags now render through `render(children)`: `CommonTag` holds the generic protocol shared by every tag class, and `Tag` overrides it with a direct fast path. (#7121)
- (radix) Stop `rx.form.message` from passing `force_match` to the DOM when `match` is not set. (#7133)
- (core) Stop the default error boundary fallback from logging invalid DOM property warnings for its SVG icon. (#7130)

Read PR #6850 (it explains `mergeSlotProps`/`mergeRefs` semantics: own props win, `on*` handlers
compose, className concatenates, style deep-merges via mergician, refs compose) and #7176.

## Build (dev AND prod; baseline the as_child/upload/svg cases on 0.9.11.post1)

1. Forms: `rx.form.root` → `rx.form.field` → `rx.form.control(<stateful control>, as_child=True)`
   for `rx.input`, `rx.text_area`, `rx.select`, `rx.checkbox`, `rx.switch`, `rx.radio_group`,
   `rx.slider` — each bound to a State var (`value=`/`checked=` + `on_change`), one bound to an
   `rx._x.client_state` var, one fully controlled (debounce path), one with an explicit `id=` and
   `style=`/`class_name=` (merge semantics!). Add `rx.form.message(match="valueMissing")` and one
   `rx.form.message` WITHOUT `match` (inspect the DOM: no `force_match`/`forceMatch` attribute).
   Submit → `on_submit` must receive every field under its `name`; inspect DOM for injected
   `name`/`id`/`aria-describedby`; type and check both the State var and the DOM value update.
2. Radix `as_child`-style parents wrapping stateful/memoized children: `rx.dialog.trigger`,
   `rx.popover.trigger`, `rx.tooltip`, `rx.dropdown_menu.trigger`, `rx.hover_card.trigger` around
   an `rx.button` whose label is a State var and which has its own `on_click`; clicking must both
   open the overlay AND run the handler (handler composition). Put one such trigger inside
   `rx.foreach` and one inside a `ComponentState`.
3. `@rx.memo` bodies containing provider-backed components: `rx.upload` (with `rx.upload_files`
   handler, id per item) inside a memo, inside a memo inside `rx.foreach`, inside a
   `ComponentState`; actually upload a file via Playwright `set_input_files` and confirm the
   handler receives it. Also a memo containing `rx.toast.provider`-needing toasts and color-mode
   consumers (`rx.color_mode_cond`).
4. `rx.el.svg` with `rx.el.defs(rx.el.linear_gradient(id=...))` referenced by `fill="url(#id)"`
   — once at top level, once inside `rx.foreach` (id per item via f-string), once inside an
   `@rx.memo`; verify the gradient actually paints (screenshot + `getComputedStyle`/`fill`
   attribute) in dev and prod.
5. Shared event chains: 100 buttons all bound to `on_click=State.bump` (bare handler), 100 bound to
   `State.bump_by(i)` (args), some with `.stop_propagation()`/`.prevent_default()` and one with a
   `.throttle(500)`/`.debounce(300)` variant, plus the same handler bound to `on_click` AND
   `on_mouse_enter` on one element. Every click must dispatch the right args and the actions must
   not leak between call sites. Grep the compiled page for how many `useCallback` wrappers exist.
6. Error boundary: a page with a component that throws at render (a custom component whose
   `add_hooks` throws, or `rx.Var("undefined.x")` in a prop); trigger it and read the browser
   console — no "Invalid DOM property" warnings for the fallback's SVG (#7130). Baseline.
7. Compile-time sanity/perf: time `reflex export --frontend-only` (or the first `reflex run`
   compile) for a page with ~500 components on 0.9.12a1 vs 0.9.11.post1; record numbers.
