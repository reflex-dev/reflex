Add `rx.vars.const()`, which binds a value to a `const` declaration in a component's hook scope and returns a `Var` referring to the bound name, along with `rx.vars.const_unpack()` and `rx.vars.const_fields()` to destructure an array or object value into several vars from a single declaration. `rx.vars.hook_fn()` returns a callable `Var` for a hook imported from a library, and `rx.vars.use_hook_var()` now forwards positional arguments to the hook call, so hooks that take arguments are supported.

```python
use_dropzone = rx.vars.hook_fn("react-dropzone", "useDropzone")
root_props, is_drag_active = rx.vars.const_fields(
    use_dropzone.call(options), "getRootProps", "isDragActive"
)
# const { getRootProps: <root_props>, isDragActive: <is_drag_active> } = useDropzone(<options>);
```

Each binding is typed by the field or index it comes from, and the hook is called once however many of its values are used. `use_hook_var()` no longer accepts the var type positionally; pass it as `_var_type=`.
