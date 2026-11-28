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
  style/lower.py, merge.py  the styles a user writes to the ones StyleX compiles
  style/emit.py             merged styles to the statements of a module
  styles/                   the look of each component, one table per module
  styles/appearance.py      by_appearance: a value that is no color, light and dark
  layout/                   the layout components, rx.ui.theme among them
  typography/               text, heading, code, blockquote, link
  components/               the other components: separator, inset, aspect_ratio
  props.py                  the values of the props many components share
  _radix_tokens.py          generated: the modules below and what they define
js/                         the javascript package, with its own tooling
  src/                      what ships: copied into an app at .web/reflex-ui/
    base.css                the cascade layer order and the color scheme switch
    class-name.js           joins the class names of compiled styles: a theme's
    vite-plugin-stylex.js   the StyleX Vite plugin, fitted to the Reflex build
    behaviors/              the little a component needs a script for
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
| A responsive list or `rx.breakpoints(...)` in a style | Media-query conditions on the app's breakpoints |
| A prop per breakpoint: `size=rx.breakpoints(initial="1", md="3")` | Media-query conditions on the breakpoints of Radix Themes: 520, 768, 1024, 1280 and 1640px |
| `rx.color("ruby", 9)` or a token | `var(--ruby-9)`, and `import "$/reflex-ui/colors/ruby.stylex.js"` in the module |
| Layout props (`gap`, `p`, `m`, `columns`, `direction`) | Styles, lowered like any other |
| `variant=State.kind` | One style per value of that prop, folded into a table of class names the element indexes: `sx_…_c + " " + (sx_…_0[state.kind] ?? sx_…_0d)` |
| `style=State.style_dict` | The inline `style` of the element; conditions are not available |
| `margin="0 auto"` | Its longhands |
| `animation_name=keyframes({...})` | A `stylex.keyframes` statement beside the declaration, which StyleX folds into the name of the animation |
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

It also holds what Radix Themes styles through a selector that a class on an
element cannot express: the selection color inside a theme and the opacity a
button gives the icons inside it (`--rx-icon-opacity`, read by every `svg` of
a theme and nothing to one outside a button), in the layer `reflex-ui.base`
so that a component's own style beats them, and the `@font-face` rules of the
system fonts whose metrics Radix adjusts, which `js/tests/base-css.test.js`
keeps equal to the ones of `@radix-ui/themes`.

And it says which appearance an element has to what `light-dark()` cannot
choose between. `--rx-if-light` and `--rx-if-dark` are set wherever the
classes `light` and `dark` are (the root, and the element around a theme with
an appearance): the one of the current appearance is invalid and the other is
empty, so `var(--rx-if-light, brightness(0.92)) var(--rx-if-dark,
brightness(1.08))` is the filter of the appearance alone. A table writes it
`by_appearance(light, dark)`, from `styles/appearance.py`.
`-webkit-text-size-adjust` is not there: the build adds the prefixed property
beside the one `themes/theme.js` sets.

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


class Button(UIComponent, elements.Button):
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

- **The element.** A component that renders one HTML element lists its class
  of `reflex_components_core.el.elements` after `UIComponent`, as the Radix
  wrapper it is forked from does. It gives the component the attributes of
  its tag as props (`title`, `tab_index`, `href`...), and nothing else.
- **Props** are fields, as on any component, and reach the element as
  attributes. A keyword argument that is not a field, an event trigger, or a
  `data_*` or `aria_*` attribute is a CSS property, and an unknown one is an
  error: `rx.ui.button: unknown CSS property "paddng". Did you mean "padding"?`
- **Variants**: a field named in `variants` or in the `props` of a `compound`
  style selects styles and is not rendered as an attribute. Its default is the
  default of the field, or the entry of `defaults` in the table for a default
  that Radix Themes has and the Reflex wrapper does not pass, such as the
  size of a heading. Bound to state, it is indexed in the browser. A variant
  wins its name over a layout prop: the `align` of text is `text-align`.
- **Layout props**: a field named after one of `LAYOUT_PROPS` (`p`, `m`, `gap`,
  `spacing`, `columns`, `direction`…) is lowered to styles before the
  element's own, and is not rendered either. Declare only those the component
  should take: on a component without a `columns` field, `columns` is the CSS
  property.
- **A value per breakpoint.** A variant or a layout prop typed `Responsive[...]`
  takes `rx.breakpoints(initial="1", md="3")`. The breakpoints are those of
  Radix Themes, whatever the breakpoints of the app, and apply mobile first.
  At each one the table is resolved again for the values the props then have,
  compound styles included, and each property that changes gets a media
  query; a property those values no longer set is `revert-layer`. A table
  needs nothing for it.
- **A value a prop does not take** is an error where the component is
  created, for every variant and layout prop whose type is a `Literal`:
  `rx.ui.text: unknown size "12". Did you mean "2"? The values are "1", ...`.
- **`as_`** names the tag. `_as_tags` lists the tags Radix Themes renders for
  the component; any other value of the prop renders the default tag, as it
  does there. `as_` can be read as a variant (`"as_": {"label": {...}}`).
- **`as_child`** renders the only child in place of the element: the tag, the
  props and the children are the child's, its props winning, with the class
  names of both. When the child is an rx.ui component the styles of both are
  merged into one declaration, the child's winning, since two sets of class
  names cannot say which one does. It is read at compile time.
- **`color_scheme`** is read by a table as `"true"` when the element has a
  color: `"variants": {"color_scheme": {"true": {...}}}`. The tokens of the
  accent resolve against that color, so a table never needs to know which.
- **`radius`**, on a component with that field, is the radius of the element
  itself, as `data-radius` is in Radix Themes: the theme of that radius and
  the steps of the radius scale, applied like the accent of a `color_scheme`.
  Declare the field (`Var[LiteralRadius]`) and write the table with
  `tokens.radius`.
- **What Radix Themes selects by ancestor**, a class on an element cannot: a
  link inside colored text, high-contrast text inside a colored element, code
  inside a link. The ancestor hands the value down in a custom property and
  the descendant reads it with a fallback, as `styles/typography.py` does.
  Every component with a `color_scheme` spreads `ACCENT_SCOPE` into that
  variant.
- **What Radix Themes resets on children**: a ghost button or card, and an
  inset, take their padding back with negative margins, which Radix computes
  through `--margin-*-override` properties that it has to reset on every
  child. Here the margins are written on the element itself (`calc(0px -
  <padding>)`) and nothing is handed down, so there is nothing to reset:
  no rx.ui element reads an inherited margin.
- **States**: a rule under `@media (hover: hover)` is placed after the ones
  for `:active` and `:focus-visible`, and a rule on an attribute
  (`[data-disabled]`) after every pseudo-class, whatever the order of the
  table. Where Radix lets a later rule win, make the conditions exclusive
  instead: `":hover:not(:active)"`, as `styles/button.py` does.
- **Pseudo-elements** (`_before`, `_after`) are the outermost block, with
  their states inside: `"_after": {"@media (hover: hover)": {":hover:not(:active)":
  {...}}}`. A style merged later keeps what the earlier one gives a
  pseudo-element and replaces everything else of a property it sets, its
  conditions included, so a variant that changes the rules of several states
  (high contrast) is the table of its variant merged block by block when the
  table is built (`_over` in `styles/button.py`), listed as a compound style.
- **A value that differs between the appearances** and is no color, such as a
  filter or the layers of a shadow, is `by_appearance(light, dark)`.
- **Animations**: `"animation_name": keyframes({"from": {...}, "to": {...}})`
  with the longhands beside it (`animation_duration`...), as StyleX drops the
  `animation` shorthand. Equal keyframes are declared once per module. Radix
  Themes does not change the spinner, the skeleton or the progress bar for
  `prefers-reduced-motion`, so neither do these.
- **Styles a class adds**: `add_style`, as in any component, applies after the
  layout props and before the styles of the app. `rx.ui.center` centers that
  way, so that `align` and `justify` lose to it as they do in `rx.center`.
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
  and value, `defaults` for the value a prop selects styles by when it is left
  out, `compound` styles for a combination of props, and `parts` for inner
  elements.
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
| Layout props (`p`, `m`, `gap`, `columns`, `direction`...) | Styles, with steps of the space scale as `var(--space-N)`, and a value per breakpoint on the breakpoints of Radix Themes |
| A shorthand bound to state, or holding `var(...)` | Kept whole; it removes its longhands from the styles before it |
| `None` | The property is unset |
| `keyframes({...})` as `animation_name` | A `Keyframes`: its frames lowered, compared and hashed by content |
| A nested selector, an unknown property, `animation` | `StyleError` |

Styles merge by property and the last one wins: base, variants, compound
styles, layout props, then the user's style. A style that sets a property only
under a condition, as a `_hover` block does, keeps the earlier value everywhere
else; one that sets it outright replaces the earlier conditions too.
`style` may be a list of styles, each merged over the ones before it.

StyleX silently drops `border`, `border_top` and its siblings, `background`
and `animation`, which is why the first two are always split and the third is
refused: an animation is its longhands, and `keyframes(frames)` as its
`animation_name`, in a table or in the `style` of an element. A split needs the value while compiling, so `background=State.color`
is an error that says to bind `background_color`, and a `background` with more
than a color or an image is one that names its longhands.

## Adding a component

What a wave does for each component, in this order. `flex` (a layout), `text`
(typography) and `separator` (neither) are the ones to copy.

1. **Read the sources.** The Radix wrapper in
   `reflex-components-radix/.../themes/` gives the API: the base classes, the
   fields with their types, defaults and docstrings, and what `create` does.
   The CSS in `js/node_modules/@radix-ui/themes/src/components/<name>.css`
   gives the look, and `<name>.props.tsx` the defaults Radix applies when a
   prop is left out and the values it falls back from.
2. **The table**, `styles/<name>.py`: one `ComponentStyles` constant, grouped
   as the CSS is (base, sizes, variants), with a one-line comment only where
   the Radix rule is not obvious. Values are tokens (`tokens.space[4]`,
   `tokens.accent.a[11]`), never a copy of what a token holds. A custom
   property Radix sets on the element (`--line-height`) stays one, so that
   what is inside the element follows it. `StyleProps` cannot type such a
   key, a free condition such as `"@media (pointer: coarse)"`, or a token on a
   property typed by its keywords (`font_style`, `cursor`): wrap a style that
   holds one in `unchecked(...)`, and the lowering checks it instead. Radix's
   default for a prop the wrapper does not default goes in `defaults`. What several tables share is
   in `styles/typography.py`.
3. **The wrapper**, `layout/`, `typography/` or `components/<name>.py`: a
   class deriving from `UIComponent` and the element class the Radix wrapper
   derives from, with `tag`, `styles` and the same fields, copied with their
   `field(doc=...)` so that the documentation and the stubs stay complete.
   Keep `create` as it is there. A second element is a `Part`.
4. **The name**: an entry of `_SUBMOD_ATTRS` in `__init__.py`, a namespace
   (`rx.ui.text`, `rx.ui.list`) under the name `rx` has it.
5. **Unit tests**, `tests/units/reflex_components_ui/<package>/test_<name>.py`:
   for a few uses, the whole rendered element and the whole style each
   element declares (the `declared_styles` fixture). The API parity test
   picks the name up by itself, members of a namespace included, and the list
   of names in `test_api_parity.py` is extended by hand.
6. **The matrix and the contract**, `parity/ui_parity/components/<name>.py`
   (see [The parity harness](#the-parity-harness)): every value of every prop,
   crossed where they interact and swept otherwise, the 26 accents as a
   sweep, dark, each interactive state the component has, a prop per
   breakpoint at the viewports around its breakpoints, and the nestings Radix
   styles specially. Hold it to zero (`threshold=0, tolerance=0`) unless
   something outside the component dithers, and say what in a comment.
7. **Run** `uv run python scripts/ui_parity.py <name>` until nothing differs.
   An intended difference is an entry of `parity/allowlist.toml` with a
   reason a user can read; anything else is a bug.
8. **The stubs**: `uv run python scripts/make_pyi.py`, and commit
   `pyi_hashes.json`.
9. **The shared app**: an element on the `/wave` page of
   `tests/integration/tests_playwright/test_ui_components.py` for what only a
   real app shows, such as a style the compile adds or a navigation.
10. **The record**: the wave's row in the run-time table below, the gzipped
    CSS and JavaScript it adds, and a news fragment in `news/`.

What the display and action wave settled, for the waves after it:

- **Zero is the first target, and the report says what kept a matrix from
  it.** Run a matrix at `threshold=0, tolerance=0` first. What is left is a
  bug unless the same props are equal in another frame: the browser dithers
  a gradient and anti-aliases a rounded ring, a turned shape or a scaled
  image by where they are on the page. Then keep the default threshold, say
  in a comment how many cells were equal at zero and what the others hold,
  and set `tolerance` no higher than what was measured.
- **A reference that settles late is no reference.** Radix Themes shows the
  fallback of an avatar and the scrollbars of a scroll area some time after
  the page is ready, so a screenshot has them or not. Leave such a cell out
  with a comment that says so, and cover the state in the contract, which
  waits for it. What settles for good is waited for instead, with the
  `ready` of its matrix: an avatar of Radix is empty until JavaScript has
  run, and so is the trigger of its select.
- **An animation is compared by the contract.** A screenshot is taken with
  animations off, and an animation that never ends is cancelled for it. A
  step reads `element.getAnimations()` on both systems and asserts the
  keyframes and the timing exactly, as the spinner and the skeleton do.
- **A native element where Radix draws its own.** `rx.ui.scroll_area` is
  one element that scrolls natively: `overflow` by the `scrollbars` prop,
  `scrollbar-width: thin` and `scrollbar-color` in the grays Radix uses. It
  needs no script and scrolls with JavaScript off; what the browser decides
  (the shape of a scrollbar, whether it takes room, when it shows) is in the
  allowlist with its reason. `rx.ui.progress` is a `div` with the ARIA of a
  progress bar rather than a `<progress>`: a plain element costs no script
  either, and the pseudo-elements a native bar is drawn with differ by
  engine, of which only Chromium could be looked at when it was written.
- **A script is the last resort, and is a function, not a component.**
  `js/src/behaviors/<name>.js` exports plain functions with JSDoc types and a
  vitest file under `js/tests/behaviors/`. A component reaches one through a
  `Var` that carries its import, such as the `ref` of the image of an
  avatar: no hook, no state, nothing rendered again, and a page without the
  component does not load it. Render both states on the server and let the
  script say which one holds (`data-status`), so that the page is right
  before it runs, and say in the contract what shows with JavaScript off.
- **What a class cannot say of the children of an element** is a rule of
  `base.css`, on an attribute the wrapper renders: `[data-rx-callout] > *`
  puts everything in a callout in its last column, `[data-rx-skeleton] > *`
  hides what a skeleton stands in for.
- **A component rendered as its child** without an `as_child` prop, as a
  skeleton around one element, sets `_as_child` itself, and
  `_merges_slot = False` when the child has to keep its own styles: each
  then declares its own, and the element has the class names of both. What
  must win over the child is `!important`, as it is in Radix Themes.
- **A prop that is a CSS property** (`width`, `min_width`...) is moved into
  the style with `props.style_props`, at the breakpoints of Radix Themes.
- **A private variant.** A table may read something that is no prop, such as
  whether a skeleton is around text: name the variant with an underscore
  (`"_inline"`) and set the attribute of that name before the component is
  initialized. Mind the names the base class uses (`_radius`, `_accent`).
- **A shorthand that some values keep whole** (`padding: calc(...)`) and
  others split does not mix across the values of one prop: StyleX resolves
  styles in the order they are written, and a whole shorthand written after
  its longhands cancels them. Write each side out, as the ghost button does.

### Behaviour: the browser first, a script for the gap

What a component does is the contract of its Radix counterpart, kept with
as little JavaScript as the browser allows. In this order:

1. **An element that already does it.** A checkbox, a radio button, a
   switch and a thumb of a slider are native inputs, drawn by their table
   with `appearance: none` and their `::before` and `::after`; an item with
   text is a `<label>` around its input; a form reads the validity the
   browser computes; the list of a select is a `popover` its trigger opens
   with `popovertarget`. The browser then gives the keys, the focus, the
   form value, the validation, the top layer and the dismissal, with
   JavaScript off too.
2. **CSS for what follows a state.** `:checked`, `:disabled`,
   `:placeholder-shown`, `:popover-open`, and `:has()` on what is around
   the control. Two conditions of one property that can both hold are
   written so that only one does (`":checked:not(:disabled)"`): StyleX
   orders rules by property, not by how they were written. What a class
   cannot select is a rule of `base.css` on a `data-rx-*` attribute.
3. **The compiler for what Radix hands down a context.** The root of a
   group finds its items while compiling (`GroupRoot` in
   `components/_group.py`, through `rx.foreach` and `rx.cond`) and gives
   each its name, its look and its state: `_join` sets private variants
   and attributes, and nothing is looked up in the browser. An item that is
   not below its root in the tree of the page, as one a memoized component
   renders, has the look of a group without props.
4. **A script, when a step of the contract fails without one** and nothing
   above gives it: the arrow keys of a segmented control, the filled part
   of the track of a slider, the messages of a form, the value and the keys
   of a select. It has this shape:
   - plain exported functions in `js/src/behaviors/<name>.js`, typed by
     JSDoc, with a vitest file that reaches every branch; no JSX, no hook,
     no React state;
   - one listener on the root for all its items (`onKeyDown`, `onClick`,
     `onInputCapture`), or a `ref` for what must run when the page renders,
     passed through `custom_attrs` as a `Var` that carries its import, so a
     page without the component does not load it. A `Var` that is only
     added in `_render` is not collected: yield it from `_get_vars`;
   - its state is the DOM: the value of a native input, an attribute. A
     value bound to state is handed to the `ref` as an argument, and the
     script shows it;
   - the server renders the right state, and the script only keeps it: the
     trigger of a select shows the text of its value before any script
     runs, where the options are known while compiling;
   - together the scripts stay under 6 kB, minified and gzipped (the table
     below). What only some browsers need is imported on demand, as
     `popup-position.js` is where `CSS.supports` finds no anchor
     positioning.
5. **The contract says it against both systems.** Every step runs on
   `rx.<name>` and on `rx.ui.<name>`; a step one of them does not pass is an
   entry of `allowlist.toml` for that system, with a reason a user can read.
   One step is on the server's HTML and one with JavaScript off, and they
   say what the page is before a script runs. A reference that goes on
   rendering after it is hydrated, as the trigger of the Radix select does,
   is waited for with the `ready` of its matrix.

**How open state reaches styles.** A popup is a native popover, and
`:popover-open` is its open state: the table of the popup selects on it,
and `@starting-style` under it is where the popup comes in from. What opens
the popup is rendered right before it, so its table selects on
`OPENS` (`styles/popup.py`): `:is([data-state='open'], :has(+ :popover-open))`.
The second half needs no script; the first is what `popupToggle` writes,
with `aria-expanded`, for assistive technology and for a trigger that
cannot be the element before its popup. `styles/popup.py` (`POPUP`,
`placements()`) and `behaviors/popup.js` are the popup the later waves
reuse: placed by CSS anchor positioning, turned over by
`position-try-fallbacks`, never taller than the room the viewport leaves.

| script | minified and gzipped | what it does |
| --- | --- | --- |
| `image-status.js` | 232 B | shows the fallback of an avatar whose image fails |
| `text-field.js` | 243 B | a press on the box of a text field focuses its input |
| `form-validity.js` | 684 B | shows the messages of a form that match the validity the browser computed |
| `roving-focus.js` | 411 B | the arrow keys of a segmented control |
| `slider.js` | 660 B | the filled part of the track, the order of several thumbs, a press on the track |
| `popup.js` | 386 B | says on a trigger that its popover is open, and gives the popups of a loop their own ids |
| `popup-position.js` | 404 B | places a popover in a browser without anchor positioning; loaded only there |
| `listbox.js` | 1,536 B | the value of a select, the keys of its list, typing to find an option |

What the form controls wave settled:

- **A component rendered from state.** Every form control but the parts of
  `rx.ui.form` has styles under a condition (`:checked`, `:disabled`,
  `:has(...)`), which code evaluated in the browser cannot apply: held in
  state as a component, each raises the `StyleError` that says to render it
  in a page and show it with `rx.cond`.
- **Generated names.** A group that is given no `name`, a segmented
  control, and the popup and the labels of a select are given an id from a
  counter while compiling. Items a `rx.foreach` renders share it: give a
  group in a loop a `name`; the script of a select tells its popups apart
  when it first runs.
- **One event for a group.** `on_change` of a group is one listener on its
  root, which reads the values of its inputs from the event.
- **An input bound to state** is rendered through `DebounceInput`, as the
  inputs of `rx.el` are: `rx.ui.input` and `rx.ui.text_area` keep the caret
  where it is while the state follows.
- **A matrix of a popup** crops the stage, opens the popup with a state of
  its own (`states={OPEN: State(...)}`), and leaves room in the stage for
  it: a popup that meets the edge of the viewport is moved by Radix and
  turned over by CSS, which is the browser's business, not a cell's.

### What a wave adds to a page

Gzipped (`gzip -9` of each file under `.web/build/client`), for an app whose
only plugin is `UIPlugin()`, against the same page without the components:

| page | JavaScript | CSS | files |
| --- | --- | --- | --- |
| one `rx.ui.button` | +405 B | +1,031 B | none |
| a button with a `color_scheme` | +659 B | +2,081 B | one shared chunk of 188 B |
| a button with a `radius` | +621 B | +1,031 B | one shared chunk of 287 B |
| the 12 components of wave 2, one accent | +3,374 B | +5,295 B | Lucide's icon chunk (783 B), as `rx.icon` alone adds |
| the 13 form controls of wave 3, one accent | +11,326 B | +10,639 B | one chunk of 404 B, `popup-position.js`, that a browser with anchor positioning never loads |

The page without components is 146,124 B of JavaScript and 6,109 B of CSS,
4.6 kB of it the theme. The script of an avatar is 231 B of the page's own
chunk. Each further literal `color_scheme` on a page is about 1.05 kB of
CSS, the scale of that color, and some 20 B of JavaScript: a page with six
colors is 5.4 kB of CSS over the one with none, and still one chunk.

The form controls were measured against a page that is 145,768 B of
JavaScript and 6,464 B of CSS. Some 4.3 kB of their JavaScript is the
scripts of the table above, and the rest the elements of the page.

Opening a select of 50 options with the keyboard, in a production build,
as the median of 15 runs of the main thread's task time (the
`TaskDuration` of the Chrome DevTools protocol, from the key to two frames
after an option has the focus):

| | main thread | of it script | at a CPU four times slower |
| --- | --- | --- | --- |
| `rx.select` | 38.8 ms | 12.5 ms | 172.5 ms |
| `rx.ui.select` | 15.6 ms | 0.7 ms | 63.7 ms |

The page of that `rx.select` loads 192,201 B of JavaScript and 88,099 B of
CSS, the one of `rx.ui.select` 151,165 B and 8,581 B.

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
import {className as reflexUIClassName} from "$/reflex-ui/class-name.js"
import {accentIndigo} from "$/reflex-ui/themes/accent/indigo.js"
import {focusScope} from "$/reflex-ui/themes/focus.js"
import {graySlate} from "$/reflex-ui/themes/gray/slate.js"
...
const sx_c1c0436182 = stylex.create({ s: {"position": "relative", "zIndex": 0, "minHeight": {...}} });
const sx_c1c0436182_c = stylex.props(sx_c1c0436182.s).className;
const sx_c1c0436182_o = sx_c1c0436182.s;
const reflexUIClasses_48dbd5f3d5 = "reflex-ui-theme " + reflexUIClassName(spaceScope, radiusScope, typographyScope, shadowScope, colorScope, focusScope, accentIndigo, graySlate, radiusLarge, scaling100, panelTranslucent, reflexUITheme.root, reflexUITheme.background, sx_c1c0436182_o);

jsx("div",{className:reflexUIClasses_48dbd5f3d5}, ...)
```

StyleX folds `stylex.props(...)` into a string only when every argument is
declared in the module that makes the call, and a theme is declared in a
module of its own. So the classes of a theme are joined when the module
loads, by `class-name.js`: what `stylex.props(...).className` does, a later
style winning a property, without the rest of the StyleX runtime, which no
page ships. The theme of the app adds 0.6 kB of gzipped javascript to the
chunk every page already loads, and no chunk. The element's own style is last,
through `sx_..._o`, the style before it is folded: it wins where a theme
element sets the same property, such as the text color.

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
the custom property in `Lowered.imports`: `VAR_MODULES` has the module of each
of the 1,070 custom properties by its whole name, built from the generated
list, and a `var()` of any other custom property, such as one an app defines,
is left alone and imports nothing. A shorthand gives a token that holds one value to its
longhands, as it does with `rx.color(...)`: `{"padding": f"{tokens.space[2]}
{tokens.space[4]}"}` becomes four paddings. A shadow and a font family are
lists, and keep the shorthand whole.

For a component:

- Write the style table with tokens, never with the color of a named scale:
  `"background_color": tokens.accent[9]`, `"color": tokens.accent.contrast`,
  `"border_radius": tokens.radius[2]`, `"height": tokens.space[6]`.
- `color_scheme` is an accent on the element itself. Declare the field,
  `color_scheme: Var[LiteralAccentColor]` from `reflex_components_ui.themes`,
  and `UIComponent` does the rest: the tokens of the table resolve against
  the accent of the element. A literal color imports its accent and
  `focusScope` and joins their classes in a constant; `"gray"` imports
  `accentGray` alone, and keeps the focus colors of the theme; a color bound
  to state imports all 26 and indexes a table of their class names, built
  when the module loads. On a component without the field, `color_scheme` is
  the CSS property. `themes.color_scheme_styles(name, value)` is what
  `UIComponent` calls.
- The space, radius, typography, shadow and `--color-*` tokens, the accent, the
  gray and the focus colors are defined wherever a theme is, which in an app is
  everywhere. A cursor, a white, and a scale named with `tokens.scale` or
  `rx.color` are defined by the module `Lowered.imports` names, which the
  module that renders the element imports.
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

### Declaring a matrix and a contract

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
   style is read when it is not the first element (a part is one selector,
   or one for each system, and may end in `::before` or `::after` where one
   system draws with a pseudo-element what the other has an element for), `stage` sizes the frame,
   `crop="stage"` compares the whole frame for what is drawn outside the
   element, and `states` adds a driver for a state the runner does not know,
   such as `open`. `ready` is a JavaScript expression a page must meet before
   it is read, for a reference that goes on rendering after it is hydrated.

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
| 1: layout and typography | 19, and `text.kbd` | 1011, 44 of them interactive | 27 s + 61 s |
| 2: display and actions | 12 | 1379, 181 of them interactive | 56 s + 178 s for both waves, 115 s of it this one |
| 3: form controls | 13 | 1514, 318 of them interactive | 115 s + 403 s for the three waves, 177 s of it this one |

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
