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
  style/lower.py, merge.py  the styles a user writes to the ones StyleX compiles
  style/emit.py             merged styles to the statements of a module
  styles/                   the look of each component, one table per module
  layout/                   the components
  _radix_tokens.py          generated: the modules below and what they define
js/                         the javascript package, with its own tooling
  src/                      what ships: copied into an app at .web/reflex-ui/
    base.css                the cascade layer order and the color scheme switch
    vite-plugin-stylex.js   the StyleX Vite plugin, fitted to the Reflex build
    colors/                 generated: one module for each Radix color scale
    tokens/                 generated: space, radius, typography, shadow, ...
    themes/                 generated: accent/<name>, gray/<name>, radius, scaling, ...
  tests/                    vitest
    harness/                the pages the live tests build and open in Chromium
  scripts/generate.js       writes and checks the generated files
  scripts/radix-tokens.js   the generator of the colors, tokens and themes
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

`rx.ui.box("hello", style={"top": "4px"})` compiles to a `div`, with its style
declared in the module that renders it:

```js
import * as stylex from "@stylexjs/stylex"

const sx_3debd41bb2 = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "top": "4px"} });
const sx_3debd41bb2_c = stylex.props(sx_3debd41bb2.s).className;

jsx("div",{className:sx_3debd41bb2_c},"hello")
```

StyleX folds the second statement into the string `"x9f619 x1lliihq xndqk7f"`
and appends the three rules to the app's stylesheet. It only does so for a
call it can evaluate while compiling, on a style declared in the same module,
so everything the compiler emits has that shape and **no page ships the StyleX
runtime**:

| You write | It becomes |
| --- | --- |
| A literal value | An atomic class in the module's constant |
| A state `Var` value | `var(--v0)` in the declaration, and `style={{"--v0": state.width ?? "initial"}}` on the element |
| A `_hover` or `:focus-visible` block | A condition on each property inside |
| A responsive list or `rx.breakpoints(...)` | Media-query conditions on the app's breakpoints |
| `rx.color("ruby", 9)` or a token | `var(--ruby-9)`, and `import "$/reflex-ui/colors/ruby.stylex.js"` in the module |
| Layout props (`gap`, `p`, `m`, `columns`, `direction`) | Styles, lowered like any other |
| `variant=State.kind` | One style per value of that prop, folded into a table of class names the element indexes: `sx_…_c + " " + (sx_…_0[state.kind] ?? sx_…_0d)` |
| `style=State.style_dict` | The inline `style` of the element; conditions are not available |
| `margin="0 auto"` | Its longhands |
| `"& > div": {...}`, `paddng="1em"` | A `StyleError` where the component is created |

What follows from it:

- A component is a subclass of `UIComponent` with a `styles` table. It imports
  nothing: `add_custom_code` emits the declaration and `add_imports` the token
  modules, which the compiler places in whichever module renders the element
  (a page, an auto-memoized element, an `rx.memo` component).
- A declaration is named after its content, so equal styles on many elements
  are declared once per module and the elements share one string.
- A value bound to state is a custom property, so the declaration stays
  literal. A number is given `px` unless the property takes bare numbers, as
  StyleX does for a literal. The browser recomputes the style of each element
  whose custom property changes: a thousand rows bound to one value that
  changes cost more than they do with Emotion, which swaps one class. Rows
  bound to a value of their own cost less.
- A prop bound to state gets, for each of its values, the whole value of the
  properties it changes, so a value replaces the others instead of overriding
  them. Props that a compound style combines, or that set the same property,
  are indexed together: `table[kind]?.[size]`. A value the table does not list
  gets the style of the element without the prop.
- The element's own `class_name` is joined to the constant: `"p-8 " + sx_…_c`.
- A component held in state is evaluated in the browser and never reaches
  StyleX: its literal styles fall back to an inline `style`, and anything
  conditional or bound to state there is a `StyleError` that says to render
  the component in a page.

`base.css` declares the cascade order once: the resets (Reflex, Tailwind's
`theme` and `base`), then `reflex-ui` (a component's styles merged with the
element's `style`), then Tailwind's `components` and `utilities`. Unlayered
CSS, such as an app's stylesheet, Emotion and Radix Themes, beats all of them.

`vite-plugin-stylex.js` hands StyleX only the statements above, not the module
around them, and compiles a module once per build although React Router
transforms it several times. A module that uses StyleX in any other way is
compiled whole.

## Writing a component

```python
BUTTON: ComponentStyles = {
    "base": {"display": "inline-flex", "border_radius": "var(--radius-2)"},
    "variants": {
        "variant": {"solid": {"color": "white"}, "soft": {"opacity": 0.8}},
        "size": {"1": {"height": "var(--space-5)"}, "2": {"height": "var(--space-6)"}},
    },
    "compound": [
        {"props": {"variant": "solid", "size": "2"}, "style": {"font_weight": 700}}
    ],
    "parts": {
        "icon": {
            "base": {"width": "1em"},
            "variants": {"size": {"2": {"width": "1.25em"}}},
        }
    },
}


class Button(UIComponent):
    """A button."""

    tag = "button"

    styles: ClassVar[ComponentStyles] = BUTTON

    # Which look the button has.
    variant: Var[Literal["solid", "soft"]] = field(default=LiteralVar.create("solid"))

    # How large the button is.
    size: Var[Literal["1", "2"]]

    # The space between the children.
    gap: Var[Responsive[Literal["1", "2", "3"]]]

    # Whether the button can be pressed.
    disabled: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        return super().create(Part.create(part="icon", tag="span"), *children, **props)
```

- **Props** are fields, as on any component, and reach the element as
  attributes. A keyword argument that is not a field, an event trigger, or a
  `data_*` or `aria_*` attribute is a CSS property, and an unknown one is an
  error: `rx.ui.button: unknown CSS property "paddng". Did you mean "padding"?`
- **Variants**: a field named in `variants` or in the `props` of a `compound`
  style selects styles and is not rendered as an attribute. Its default is the
  default of the field. Bound to state, it is indexed in the browser.
- **Layout props**: a field named after one of `LAYOUT_PROPS` (`p`, `m`, `gap`,
  `columns`, `direction`…) is lowered to styles before the element's own, and
  is not rendered either. Declare only those the component should take: on a
  component without a `columns` field, `columns` is the CSS property.
- **Parts**: an inner element is a `Part` named after an entry of `parts`,
  created as a child of the component or of another part. It reads the props
  of the component, takes no styles of its own, and is a `StyleError` anywhere
  else. Subclass `Part` for an inner element with fields of its own.
- **Order**: base, variants, compound styles, layout props, the styles of the
  app for the component (`rx.App(style={Button: {...}})`), then the element's
  `style` with its CSS keyword arguments written over it key by key, as in any
  Reflex component.
- The stubs type `style` as `Sequence[StyleProps] | StyleProps |
  Var[Mapping[str, Any]] | Breakpoints` through `UIComponent._pyi_overwrite_types`,
  so a misspelt property or keyword in a `style` is a type error. Keyword
  arguments stay open, as `data_*` and `aria_*` come through them: a misspelt
  one is caught by the compile.

## Styles

`reflex_components_ui.style` holds what turns the styles a user writes into
the style objects StyleX compiles. Nothing in it depends on a component.

- `StyleProps` types one style: the CSS properties under the snake_case names
  Reflex users write, the keywords of each one, and blocks under a condition
  such as `_hover` or `":focus-visible"`. `style/_css_props.py` is generated
  from the type definitions of the pinned StyleX by `js/scripts/css-props.js`.
  At runtime the name is a plain `dict`: only a type checker reads the table.
- `ComponentStyles` types the look of a component: `base`, `variants` by prop
  and value, `compound` styles for a combination of props, and `parts` for
  inner elements.
- `lower(name, style, layout)` returns a `Lowered`: `style` maps a camelCase
  CSS property to a literal, a `Var` or a condition map such as
  `{"default": v, ":hover": v, "@media ...": v}`; `imports` names the modules
  whose CSS the values need, such as a color scale; `inline` carries a `Var`
  that holds a whole dict of styles.
- `merge(name, styles, props, style, layout)` returns a `Merged`: the `style`
  of the element with every prop known at compile time resolved, `dynamic`
  alternatives for the props bound to state, and the `Merged` of each part.
  The table is lowered once and kept by identity, so it is a module constant.
- `emit(merged)` returns an `Emitted`: the statements the module declares, the
  constant and the lookups that give the element its class names, the custom
  properties of its inline style, and the modules to import.

Both results are hashable and equal when they compile to the same
declarations. Errors are `StyleError`s that start with the display name passed
as `name`, such as `rx.ui.card: unknown CSS property "paddng". Did you mean
"padding"?`.

What lowering does to each input:

| Input | Lowered form |
| --- | --- |
| A literal | The literal |
| A `Var`, or a string with one inside | The `Var` |
| `_hover`, `":hover"`, `"[data-open]"`, `"@media ..."` blocks | A condition on each property inside |
| A list or `rx.breakpoints(...)` | Conditions `@media screen and (min-width: ...)` on the app's breakpoints |
| `rx.color("ruby", 9)` | `var(--ruby-9)`, and the ruby module in `imports` |
| `margin`, `padding`, `inset`, `gap`, `overflow`, `border_width`, `border_radius`... | Their longhands |
| `border`, `border_top`..., `background` | Their longhands always: StyleX compiles neither |
| `padding_x`, `margin_y`, `bg`, `bg_color` | The properties they stand for |
| Layout props (`p`, `m`, `gap`, `columns`, `direction`...) | Styles, with steps of the space scale as `var(--space-N)` |
| A shorthand bound to state, or holding `var(...)` | Kept whole; it removes its longhands from the styles before it |
| `None` | The property is unset |
| A nested selector, an unknown property, `animation` | `StyleError` |

Styles merge by property and the last one wins: base, variants, compound
styles, layout props, then the user's style. A style that sets a property only
under a condition, as a `_hover` block does, keeps the earlier value everywhere
else; one that sets it outright replaces the earlier conditions too.
`style` may be a list of styles, each merged over the ones before it.

StyleX silently drops `border`, `border_top` and its siblings, `background`
and `animation`, which is why the first two are always split and the third is
refused. A split needs the value while compiling, so `background=State.color`
is an error that says to bind `background_color`, and a `background` with more
than a color or an image is one that names its longhands.

## Working on it

From the repository root:

```
uv run pytest tests/units/reflex_components_ui tests/units/test_init.py tests/units/test_build_config.py   # python tests
uv run python scripts/make_pyi.py                               # regenerate the .pyi stubs
npm --prefix packages/reflex-components-ui/js ci                # install the javascript tooling
npm --prefix packages/reflex-components-ui/js run check         # lint, type-check, generated files, tests: what CI runs
npm --prefix packages/reflex-components-ui/js run generate      # rewrite the generated files
uv run pytest tests/integration/tests_playwright/test_ui_components.py   # a real app in dev and prod: needs network for the npm packages
npm --prefix packages/reflex-components-ui/js run sweep         # the whole token sweep against Radix Themes, about four minutes
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
viewport are fixed, the page is hydrated (an effect of the first render has
run, so the root committed) and its fonts loaded before it is read, a style
or script tag beside a component is never taken for it, transitions and animations are off, and the "Built with Reflex" badge is
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

## Tokens and themes

Every design token is a CSS custom property with the name and the value
[Radix Themes](https://www.radix-ui.com/themes) gives it, so that a page can
mix these components with the Radix ones and show one palette.
`js/scripts/radix-tokens.js` generates them from the token stylesheet of the
`@radix-ui/themes` the Radix components install, as StyleX modules: a module
adds its CSS to an app only when something imports it.

- `colors/<scale>.stylex.js` defines a color scale. A color is one
  `light-dark()` value, with a display-P3 one for the screens that have it.
- `tokens/*.stylex.js` define the other tokens, and the variables a theme sets:
  `accent`, `gray`, `focus`, `scaling`, `radiusFactor` and `panel`. No accent
  and no gray is defined outside a theme.
- `themes/accent/<name>.js`, `themes/gray/<name>.js`, `themes/radius.js`,
  `themes/scaling.js` and `themes/panel.js` export a StyleX theme for each value
  of a prop of the Radix `Theme`. They are `.js` and not `.stylex.js`: StyleX
  keeps that extension for modules that only define variables.
- `themes/scope.js` and `themes/focus.js` are what make an element a theme. A
  token such as `--space-1` reads `--scaling`, and a custom property takes the
  value it reads from the element it is declared on. A StyleX theme declares
  its whole group again on its element, so a scope theme overrides nothing and
  is applied wherever a theme changes what the group reads. An accent on a
  single element needs `focusScope` only.
- `themes/theme.js` holds the styles of a theme element itself: `root`,
  `background`, and `light` and `dark`, which set `color-scheme`.

An appearance is the `color-scheme` of an element. The stylesheet every page
loads has to set it for `html.light` and `html.dark`, as
`js/tests/harness/base.css` does for the tests; a nested appearance is
`theme.light` or `theme.dark` on its element. Nothing else changes between the
two, and nothing here depends on being at the root: a popover or a dialog in
the top layer inherits from where it is declared.

Two things differ from Radix, both by construction:

- `--shadow-1` to `--shadow-6` list the layers of both appearances, and a layer
  the current appearance does not have is `transparent`. It paints the same.
- A nested theme that sets a gray while it inherits the gray accent has to name
  the gray accent again. Radix knows what a nested `Theme` inherits; the
  cascade does not.

`npm test` reads every custom property Radix defines under both, in headless
Chromium, for each value of each theme prop. `npm run sweep` does it for the
whole product of accent, gray, appearance, radius and scaling: 10,556 themes on
an sRGB screen and on a display-P3 one. A value that is allowed to differ is
listed with its reason in `js/tests/harness/exceptions.js`. The tests need
Chromium: `npx playwright install chromium` in `js/`.

To move to another version of Radix Themes, change `RADIX_THEMES_PACKAGE` in
`reflex-components-radix` and the pin in `js/package.json` together, then run
`npm run generate` and `npm run sweep`.

`js/tests/lint.test.js` lints a file that breaks each rule, so a rule that stops
matching fails a test.
