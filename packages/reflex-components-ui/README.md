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
