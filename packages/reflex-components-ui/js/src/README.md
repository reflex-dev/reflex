# reflex-ui

The javascript `rx.ui` components are compiled against. `rx.plugins.UIPlugin`
copies this directory into an app's `.web/reflex-ui/` from the
`reflex-components-ui` package on every compile, so an edit made here in an app
is overwritten.

- `base.css` is imported first by the app's stylesheet: it orders the cascade
  layers, switches the color scheme, and holds the selection color of a theme
  and the font faces the typography tokens name.
- `class-name.js` joins the class names of compiled styles where StyleX
  cannot fold them into a string: on an element that carries a theme.
- `colors/`, `tokens/` and `themes/` are the design tokens and the themes, as
  StyleX modules: a module adds its CSS when a page imports it.
- `behaviors/` holds the little a component needs a script for, each in a
  module a page imports only with that component: `image-status.js` tells an
  avatar how the load of its image ended.
- `vite-plugin-stylex.js` is the plugin `vite.config.js` loads to compile the
  styles.

The source, its tests and its rules live in
[`packages/reflex-components-ui/js`](https://github.com/reflex-dev/reflex/tree/main/packages/reflex-components-ui/js).
