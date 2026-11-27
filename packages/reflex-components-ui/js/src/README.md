# reflex-ui

The javascript `rx.ui` components are compiled against. `rx.plugins.UIPlugin`
copies this directory into an app's `.web/reflex-ui/` from the
`reflex-components-ui` package on every compile, so an edit made here in an app
is overwritten.

- `base.css` is imported first by the app's stylesheet: it orders the cascade
  layers and switches the color scheme.
- `vite-plugin-stylex.js` is the plugin `vite.config.js` loads to compile the
  styles.

The source, its tests and its rules live in
[`packages/reflex-components-ui/js`](https://github.com/reflex-dev/reflex/tree/main/packages/reflex-components-ui/js).
