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
