# reflex-components-ui

Reflex components that compile to plain HTML elements with static class names.
The styles are compiled by [StyleX](https://stylexjs.com) in the app's own Vite
build, and behaviour comes from the browser and a few small hooks, so no
component library ships to the browser.

The package is a pre-release. It is an optional extra of Reflex, exposed as
`rx.ui`, and its components need the plugin that compiles their styles:

```
pip install 'reflex[ui]'
```

```python
# rxconfig.py
config = rx.Config(app_name="shop", plugins=[rx.plugins.UIPlugin()])
```

Without the plugin a compile stops with `rx.ui components need
rx.plugins.UIPlugin() in rxconfig.py plugins.`

## Layout

```
src/reflex_components_ui/   the python package: the rx.ui namespace
  plugin.py                 UIPlugin: the build wiring of an app
  base.py                   UIComponent: a plain element and its StyleX source
  style/emit.py             a lowered style to a stylex.create declaration
  styles/                   the look of each component, one table per module
  layout/                   the components
js/                         the javascript package, with its own tooling
  src/                      what ships: copied into an app at .web/reflex-ui/
    base.css                the cascade layer order and the color scheme switch
    vite-plugin-stylex.js   the StyleX Vite plugin, fitted to the Reflex build
  tests/                    vitest
  scripts/generate.js       writes and checks the generated files
parity/                     the parity harness: is a component the Radix one? Not shipped
  ui_parity/components/     the matrix and the contract of each component
  allowlist.toml            every intended difference from Radix, with its reason
hatch_build.py              embeds js/src in the wheel
```

`js/` is not published to npm. A wheel embeds `js/src` as
`reflex_components_ui/js/src`; in a checkout
`reflex_components_ui.constants.JS_SRC` resolves to `js/src` directly, so an
edit needs no rebuild. A change under `js/src` is a change to this package: its
news fragment goes in `news/`.

## How a component reaches the browser

`rx.ui.box("hello", style={"padding": "4px"})` compiles to a `div`, with its
style declared in the module that renders it:

```js
import * as stylex from "@stylexjs/stylex"

const sx_f49d6b3475 = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "padding": "4px"} });

jsx("div",{...stylex.props(sx_f49d6b3475.s)},"hello")
```

StyleX then folds the call into `className: "x9f619 x1lliihq xfawy5m"` and
appends the three rules to the app's stylesheet. It only does so for a style
declared in the same module as the element, with literal arguments, so:

- A component is a subclass of `UIComponent` with a `styles` table. It imports
  nothing: `add_custom_code` emits the declaration, which the compiler places
  in whichever module renders the element (a page, or the module of a memo).
- A declaration is named after its content, so equal styles on many elements
  are declared once per module.
- A literal `class_name` is folded into the same string. One bound to state is
  joined to it at runtime.
- A component held in state is evaluated in the browser and never reaches
  StyleX: its styles fall back to an inline `style`, and a conditional style
  there is a compile error.

`base.css` declares the cascade order once: the resets (Reflex, Tailwind's
`theme` and `base`), then `reflex-ui` (a component's styles merged with the
element's `style`), then Tailwind's `components` and `utilities`. Unlayered
CSS, such as an app's stylesheet, Emotion and Radix Themes, beats all of them.

Until the style package lands (`style/lower.py`, `style/merge.py`), a `style`
takes flat properties with literal values, and `_lower_literal_styles` in
`base.py` stands in for it.

## Working on it

From the repository root:

```
uv run pytest tests/units/reflex_components_ui tests/units/test_init.py tests/units/test_build_config.py   # python tests
uv run python scripts/make_pyi.py                               # regenerate the .pyi stubs
npm --prefix packages/reflex-components-ui/js ci                # install the javascript tooling
npm --prefix packages/reflex-components-ui/js run check         # lint, type-check, generated files, tests: what CI runs
npm --prefix packages/reflex-components-ui/js run generate      # rewrite the generated files
uv run pytest tests/integration/tests_playwright/test_ui_components.py   # a real app in dev and prod: needs network for the npm packages
```

The integration test builds one shared app (`UIComponentsApp`) with Tailwind
beside the plugin and reads computed styles, the prerendered page with
JavaScript off, and the files of the production build. Add a page or an
element to that app for a new component rather than a new app.

`run check` is `run lint` (ESLint), `run typecheck` (`tsc` over the JSDoc,
nothing emitted), `run generate:check` and `test` (vitest), which also run on
their own.

## The parity harness

`rx.button(...)` becomes `rx.ui.button(...)` with the same arguments, the same
look and the same behaviour. `parity/` checks that by machine:

```
uv run python scripts/ui_parity.py box            # one component, in Chromium
uv run python scripts/ui_parity.py                # every component, in Chromium
uv run python scripts/ui_parity.py --all-engines  # and in Firefox and WebKit
uv run python scripts/ui_parity.py differences    # the intended differences, as markdown
uv run pytest tests/units/reflex_components_ui    # the API parity test, and the harness's own tests
```

Other arguments go to pytest (`-x`, `-k`), and `--engine firefox` picks one
engine. The browsers come from `uv run playwright install chromium firefox webkit`.
The command builds one production app from the declarations in
`parity/ui_parity/components/` and runs
`tests/integration/tests_playwright/test_ui_parity.py` against it:

- **Look** (`test_matrix`). A page per component renders every element of its
  matrix twice, the Radix component beside the rx.ui one, each in a frame of a
  fixed size. Per cell the harness compares the pixels (anti-aliasing ignored),
  the computed style on a list of properties, and the accessibility tree.
- **Behaviour** (`test_contract`). Each step of a component's contract runs on a
  page of its own, against the Radix component and against the rx.ui one, in
  each engine asked for.
- **API** (`tests/units/reflex_components_ui/test_api_parity.py`). The props,
  their types and literal values, and the event triggers of every name in
  `rx.ui` are those of the same name in `rx`.

A failure names what differed, by how much, and where to look:

```
box [chromium] cell base@hover:
  - 712 of 10304 pixels differ (6.91%, 0.00% allowed)
  - padding-top: rx '0px', rx.ui '3px'
  images: .../parity/report/chromium/box/base@hover.{reference,candidate,diff}.png
box [rx.ui, webkit] step "Space toggles" failed: AssertionError: ...
```

The run writes a report to `parity/report/` (or `--report DIR`): `index.html`
shows the reference, the candidate and the diff of every cell with its numbers,
grouped by component, `results.json` holds the same numbers and `timings.json`
the run time. The directory is self-contained: zip it or publish it for review.
CI uploads it as the `ui-parity-report` artifact of the `ui-parity` job.

To look at the pages by hand, `cd packages/reflex-components-ui/parity` and
`uv run reflex run`: `/parity/<component>` and `/contract/<component>/<rx|ui>`.

### Adding a component

A component wave adds, beside the wrapper and its style table, one module:
`parity/ui_parity/components/<name>.py`. It is found by its place; nothing
registers it.

1. Declare the matrix. Dimensions are props, or `appearance`, `state` and
   `viewport`, which the runner provides. `cross` takes every combination,
   `sweep` varies one dimension at a time from `base`, and `groups` adds
   further small cross products. Cross what interacts (variant with size), and
   sweep the rest (32 colors, radius, contrast): a full product does not fit
   the run-time budget.

   ```python
   MATRIX = Matrix(
       component="button",
       render=lambda namespace, props: namespace.button("Save", **props),
       base={"variant": "solid", "size": "2"},
       cross={"variant": ["solid", "soft", "outline"], "size": ["1", "2", "3"]},
       sweep={
           "color_scheme": ["tomato", "indigo", "gray"],
           "high_contrast": [True],
           "disabled": [True],
           "size": {"responsive": {"initial": "1", "md": "3"}},
           "appearance": [DARK],
           "state": [HOVER, FOCUS_VISIBLE, ACTIVE],
           "viewport": [520],
       },
       groups=[{"variant": ["soft", "outline"], "state": [HOVER], "appearance": [DARK]}],
   )
   ```

   A cell is named after what differs from the base: `size-1_variant-soft`,
   `base@dark@hover`. `target` and `parts` name the elements whose computed
   style is read when it is not the first element, `stage` sizes the frame,
   `crop="stage"` compares the whole frame for what is drawn outside the
   element, and `states` adds a driver for a state the runner does not know,
   such as `open`.

2. Declare the contract: what `render` shows, then one step per requirement.
   A step runs on the server's HTML (`SERVER`), on the page with scripts off
   (`NO_JAVASCRIPT`) or on the hydrated page (the default), and is a plain
   function that drives `run.page` and asserts. Every contract already has the
   step "hydrates with no warnings".

   ```python
   CONTRACT = Contract(
       component="switch",
       render=lambda namespace: namespace.switch(id="switch"),
   )


   @CONTRACT.step("Space toggles")
   def _space(run: Run) -> None:
       switch = run.page.locator("#switch")
       switch.focus()
       run.page.keyboard.press("Space")
       assert switch.get_attribute("aria-checked") == "true"
   ```

3. Run `uv run python scripts/ui_parity.py <name>` and open
   `parity/report/index.html`. Fix every difference, or, when it is intended,
   list it in `parity/allowlist.toml` with a reason written for a user: under
   `[[api]]`, `[[contract]]` (per system, per engine where needed) or
   `[[look]]`. A listed difference passes; an entry nothing matches any more
   fails, so the file stays the complete list, and the migration guide is
   generated from it.

4. Run `--all-engines` before the wave is reviewed, and add the wave's run
   time to the table below.

### What keeps a pixel from flaking

Both systems are on one page, in frames on the pixel grid, and are cropped by
the same rectangle relative to their frame. The device scale factor and the
viewport are fixed, the page is hydrated and its fonts loaded before it is
read, transitions and animations are off, and the "Built with Reflex" badge is
not rendered. Hover, focus and active are driven through the pointer and the
keyboard, never by a class, and the run stops if an element does not match
`:hover`, `:focus-visible` or `:active` when it should. The CI jobs do not
rerun a failure.

A pixel differs when its color is off by more than `threshold` (0.01 of the
distance from black to white, about two steps of a channel: the browser
dithers by position) and it is not on an anti-aliased edge; a cell fails above
`tolerance` (0.5% of its pixels). A matrix may tighten both, as the box does.

### Run time

The build and every matrix together must take under 15 minutes
(`UI_PARITY_BUDGET_SECONDS`), or `test_run_time_is_within_budget` fails. The
cells at rest of a page load are read from one screenshot and one script
call; an interactive cell is driven on its own. Measured in Chromium on the
development container, with boxes:

| cells at rest | interactive cells | page loads | build | matrix |
| --- | --- | --- | --- | --- |
| 100 | 0 | 1 | 6 s | 1.1 s |
| 1000 | 0 | 1 | 14 s | 15.6 s |
| 100 | 100 | 1 | 6 s | 14.5 s |
| 1000 | 300 | 1 | 18 s | 58.5 s |

So a cell at rest costs 11 to 16 ms (growing with the length of the page), an
interactive cell about 0.14 s, and a page load (one per viewport and
appearance) about 0.3 s. Keep interactive states to a sweep or a small group.

| wave | components | cells | Chromium, build + matrices |
| --- | --- | --- | --- |
| harness | box | 8 | 5 s + 1.1 s |

## Rules the tooling enforces

- **No React components in `js/src`.** Markup comes from the Python wrappers.
  JSX fails the lint everywhere except `js/tests/behaviors/`, and so do the
  imports that build a component without it.
- **No barrel files in `js/src`.** A re-export makes the CSS of everything it
  names part of whatever imports one name from it.
- **StyleX's lint rules** apply to `js/src`, and its packages are pinned to one
  exact version: StyleX is 0.x and has broken its output in a patch release.
  `tests/units/reflex_components_ui/test_js_package.py` fails when a pin moves
  alone.
- **Generated files are committed.** Each has an entry in `GENERATED` in
  `js/scripts/generate.js`; CI fails when a committed file is not what its
  generator produces.
- A lint rule in `js/src` cannot be switched off with a comment.

`js/tests/lint.test.js` lints a file that breaks each rule, so a rule that stops
matching fails a test.
