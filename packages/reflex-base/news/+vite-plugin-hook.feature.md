A plugin can add Vite plugins to the generated `vite.config.js` by overriding `Plugin.get_vite_plugins()`, instead of rewriting the file in `pre_compile`. Each `VitePluginEntry` gives the import statements it needs and the expression placed in the `plugins` array, ahead of `reactRouter()`:

```python
def get_vite_plugins(self, **context):
    return [
        VitePluginEntry(
            imports=['import inspect from "vite-plugin-inspect"'],
            call="inspect({ build: true })",
        )
    ]
```
