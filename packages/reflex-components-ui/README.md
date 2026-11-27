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
  plugin.py                 UIPlugin: the build wiring of an app, and its theme
  base.py                   UIComponent: a plain element and its StyleX source
  themes.py                 Theme: the options of a theme and the StyleX themes they apply
  tokens.py                 rx.ui.tokens: the design tokens as style values
  style/emit.py             a lowered style to a stylex.create declaration
  styles/                   the look of each component, one table per module
  layout/                   the components, rx.ui.theme among them
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

It also holds what Radix Themes styles through a selector that a class on an
element cannot express: the selection color inside a theme, in the layer
`reflex-ui.base` so that a component's own style beats it, and the
`@font-face` rules of the system fonts whose metrics Radix adjusts, which
`js/tests/base-css.test.js` keeps equal to the ones of `@radix-ui/themes`.
`-webkit-text-size-adjust` is not there: the build adds the prefixed property
beside the one `themes/theme.js` sets.

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

## Themes and tokens

The plugin takes the theme of the app. Every option has the values and, the
accent aside, the default of the `Theme` of Radix Themes:

```python
# rxconfig.py
config = rx.Config(
    app_name="shop",
    plugins=[
        rx.plugins.UIPlugin(theme=rx.ui.Theme(accent_color="indigo", radius="large"))
    ],
)
```

| Option | Values | Default |
| --- | --- | --- |
| `accent_color` | the 26 accents, `"gray"` among them | `"blue"`, as `rx.theme` has in Reflex (Radix Themes has `"indigo"`) |
| `gray_color` | `"auto"`, `"gray"`, `"mauve"`, `"slate"`, `"sage"`, `"olive"`, `"sand"` | `"auto"`: the gray that matches the accent |
| `radius` | `"none"`, `"small"`, `"medium"`, `"large"`, `"full"` | `"medium"` |
| `scaling` | `"90%"`, `"95%"`, `"100%"`, `"105%"`, `"110%"` | `"100%"` |
| `appearance` | `"inherit"`, `"light"`, `"dark"` | `"inherit"`: the color mode of the app |
| `panel_background` | `"solid"`, `"translucent"` | `"translucent"` |
| `has_background` | `True`, `False` | `True` |

A value an option does not take stops the app where `rxconfig.py` is loaded:
`rx.ui.Theme: unknown accent_color "indgo". Did you mean "indigo"? The values
are "tomato", "red", ...`. The types are `Literal`s, so a type checker says the
same.

The plugin wraps every page in one element that carries the theme, inside the
`Theme` of Radix Themes when the app has both, so a page with components of
both follows this one. It is a `div` with the class of a StyleX theme for each
option, and the only thing imported for an accent is the module of that accent:

```js
import {accentIndigo} from "$/reflex-ui/themes/accent/indigo.js"
import {focusScope} from "$/reflex-ui/themes/focus.js"
import {graySlate} from "$/reflex-ui/themes/gray/slate.js"
...
jsx("div",{...stylex.props(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, accentIndigo, graySlate, radiusLarge, scaling100, panelTranslucent, reflexUITheme.root, reflexUITheme.background, sx_c1c0436182.s, { $$css: true, className: "reflex-ui-theme" })}, ...)
```

A theme imported from another module is not folded into a string: the call
stays, and with it the 1.2 kB of the StyleX runtime, in the chunk every page
already loads.

`rx.ui.theme(...)` is the same element around part of a page. It takes the
same options, each one optional: what it leaves out is inherited.

```python
rx.ui.theme(card(), accent_color="red", radius="full")
rx.ui.theme(sidebar(), appearance="dark")
rx.ui.theme(preview(), accent_color=Settings.accent)
```

- An accent keeps the gray around it. `gray_color="auto"` with an accent is
  the gray that matches it.
- The cascade does not tell an element what it inherits, so where that matters
  a nested theme takes the theme of the app to be what is around it:
  `gray_color="auto"` without an accent matches the accent of the app, and a
  gray without an accent names the gray accent again when the app has it.
  Inside another nested theme, give both options.
- A theme with an appearance paints its background, unless
  `has_background=False`. The classes `light` and `dark`, which Tailwind and
  Radix Themes select on, go on an element around it that has no box
  (`display: contents`), so their components inside follow the appearance.
  Beside Radix Themes, give such a theme its `gray_color` too: the Radix
  stylesheet sets its plain gray wherever one of the two classes is.
- An option bound to state imports every theme it could name and chooses among
  them in the browser. For the accent that is all 26 scales: about 21 kB of
  gzipped CSS and 0.5 kB of gzipped javascript more than a literal accent,
  where the theme of the app, one accent and one gray, is 4.6 kB of gzipped
  CSS. The theme of the app is compiled ahead of time and takes literals only.
- The appearance of the theme of the app pins the page to it. It does not
  change the color mode the app starts in, which `default_color_mode` sets.
- A theme held in state is a compile error: its code never reaches StyleX.

`rx.ui.tokens` names every design token. A token is the `var()` of a custom
property, as a plain `str`, so it goes wherever a CSS value does, in the
`style` of any component and in a style table:

```python
tokens = rx.ui.tokens

tokens.space[4]  # "var(--space-4)", steps 1 to 9
tokens.radius[3]  # steps 1 to 6, and .full, .thumb, .factor
tokens.shadow[3]  # steps 1 to 6
tokens.font_size[2]  # steps 1 to 9, as line_height and letter_spacing
tokens.font_weight.bold  # light, regular, medium, bold
tokens.accent[9]  # steps 1 to 12 of the accent of the theme
tokens.accent.a[3]  # its translucent steps
tokens.accent.contrast  # and .surface, .indicator, .track
tokens.gray[11]  # the gray of the theme, like the accent
tokens.focus[8]  # the focus ring, and tokens.focus.a
tokens.color.panel  # background, overlay, surface, panel_solid, ...
tokens.cursor.button  # checkbox, disabled, link, menu_item, radio, ...
tokens.scale("ruby")[9]  # a scale by name, whatever the theme
tokens.black.a[6]  # and tokens.white.a
tokens.default.font_family  # and heading, code, strong, em, quote, tab
tokens.scaling  # "var(--scaling)"
```

A step or a name that does not exist is an error to a type checker, and a
`TokenError` that says what exists: `rx.ui.tokens.space has no step 10. Its
steps are 1 to 9.`

`lower` reads a token like any other string. It names the module that defines
the custom property in `Lowered.imports` (`VAR_MODULES`, which is built from
the generated list), and a shorthand gives a token that holds one value to its
longhands, as it does with `rx.color(...)`: `{"padding": f"{tokens.space[2]}
{tokens.space[4]}"}` becomes four paddings. A shadow and a font family are
lists, and keep the shorthand whole.

For a component:

- Write the style table with tokens, never with the color of a named scale:
  `"background_color": tokens.accent[9]`, `"color": tokens.accent.contrast`,
  `"border_radius": tokens.radius[2]`, `"height": tokens.space[6]`.
- `color_scheme` is an accent on the element itself.
  `themes.color_scheme_styles(name, value)` returns what the element needs:
  the arguments to add to its `stylex.props` call (`accentRed` and
  `focusScope`; `accentGray` alone for gray), the imports
  (`import_dict()`), and for a value bound to state the map of all 26 accents
  to declare in the module. The tokens of the table then resolve against the
  accent of the element.
- The space, radius, typography, shadow and `--color-*` tokens, the accent, the
  gray and the focus colors are defined wherever a theme is, which in an app is
  everywhere. A cursor, a black or a white, and a scale named with
  `tokens.scale` or `rx.color` are defined by the module `Lowered.imports`
  names, once the element that uses them imports it.
- A color is one `light-dark()` value: `getPropertyValue("--accent-9")` in the
  browser returns the pair, and a computed `color` the one in use.

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

## The modules behind the tokens and themes

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

An appearance is the `color-scheme` of an element. `base.css` sets it for
`html.light` and `html.dark`, the classes of the color mode of an app, as
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
