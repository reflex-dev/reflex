Add `rx.plugins.UIPlugin` and the first component, `rx.ui.box`: a plain `<div>` whose styles StyleX compiles into the app's stylesheet, so the page ships class names and no styling runtime. Add the plugin to use any `rx.ui` component:

```python
config = rx.Config(app_name="shop", plugins=[rx.plugins.UIPlugin()])
```

A box takes literal `style` values for now; a Tailwind utility in `class_name` overrides them, and an app stylesheet overrides both.
