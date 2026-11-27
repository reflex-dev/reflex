# reflex-components-ui

Reflex components that compile to plain HTML elements with static class names.
The styles are compiled by [StyleX](https://stylexjs.com) in the app's own Vite
build, and behaviour comes from the browser and a few small hooks, so no
component library ships to the browser.

The package is a pre-release and has no components yet. It is an optional extra
of Reflex, exposed as `rx.ui`:

```
pip install 'reflex[ui]'
```

## Layout

```
src/reflex_components_ui/   the python package: the rx.ui namespace
  _radix_tokens.py          generated: the modules below and what they define
js/                         the javascript package, with its own tooling
  src/                      what ships: copied into an app at .web/reflex-ui/
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

## Working on it

From the repository root:

```
uv run pytest tests/units/reflex_components_ui tests/units/test_init.py tests/units/test_build_config.py   # python tests
uv run python scripts/make_pyi.py                               # regenerate the .pyi stubs
npm --prefix packages/reflex-components-ui/js ci                # install the javascript tooling
npm --prefix packages/reflex-components-ui/js run check         # lint, type-check, generated files, tests: what CI runs
npm --prefix packages/reflex-components-ui/js run generate      # rewrite the generated files
npm --prefix packages/reflex-components-ui/js run sweep         # the whole token sweep against Radix Themes, about four minutes
```

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
