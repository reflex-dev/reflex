# Custom Code and Hooks

When wrapping a React component, you may need to define custom code or hooks that are specific to the component. This is done by defining the `add_custom_code`or `add_hooks` methods in your component class.

## Custom Code

Custom code is any JS code that need to be included in your page, but not necessarily in the component itself. This can include things like CSS styles, JS libraries, or any other code that needs to be included in the page.

```python
class CustomCodeComponent(MyBaseComponent):
    """MyComponent."""

    def add_custom_code(self) -> list[str]:
        """Add custom code to the component."""
        code1 = """const customVariable = "Custom code1";"""
        code2 = """console.log(customVariable);"""

        return [code1, code2]
```

The above example will render the following JS code in the page:

```javascript
/* import here */

const customVariable = "Custom code1";
console.log(customVariable);

/* rest of the page code */
```

## Custom Hooks

Custom hooks are any hooks that need to be included in your component. This can include things like `useEffect`, `useState`, or any other hooks from the library you are wrapping.

- Simple hooks can be added as strings.
- Hooks that need an import can be added as `rx.Var` with a `VarData` object. The `imports` attribute of the `VarData` object specifies any imports that need to be included in the component.

Hooks render in the order they are declared. The hooks the framework manages (refs, `on_mount`, and the state hooks that props read) come first, then the hooks returned by `add_hooks` in the order of the list, with a base class's hooks before a subclass's.

```python
from reflex.vars.base import Var, VarData
from reflex.components.el.elements import Div


class ComponentWithHooks(Div, MyBaseComponent):
    """MyComponent."""

    def add_hooks(self) -> list[str | Var]:
        """Add hooks to the component."""
        hooks = []
        hooks1 = """const customHookVariable = "some value";"""
        hooks.append(hooks1)

        # A hook that reads the variable declared by the hook before it.
        hooks2 = Var(
            """useEffect(() => {
                console.log(customHookVariable);
            }, []);
            """,
            _var_data=VarData(
                imports={
                    "react": ["useEffect"],
                },
            ),
        )
        hooks.append(hooks2)
        return hooks
```

The `ComponentWithHooks` will be rendered in the component in the following way:

```javascript
export function Div_7178f430b7b371af8a12d8265d65ab9b() {
  const customHookVariable = "some value";

  useEffect(() => {
    console.log(customHookVariable);
  }, []);

  return jsx("div", {});
}
```

### Hooks that read other hooks

When a hook reads a value that another hook declares, list that declaration in the `hooks` attribute of its `VarData`. Each entry maps a hook's code to its own `VarData` (or `None`). A hook's dependencies always render before it, in whichever component the hook ends up in, so a hook `Var` can be reused across components or passed in through a prop without caring about where its dependency is declared.

```python
from reflex.vars.base import Var, VarData
from reflex.components.el.elements import Div


class CountLogger(Div, MyBaseComponent):
    """MyComponent."""

    def add_hooks(self) -> list[str | Var]:
        """Add hooks to the component."""
        use_count = VarData(
            imports={"react": ["useState"]},
        )
        log_count = Var(
            """useEffect(() => {
                console.log(count);
            }, [count]);
            """,
            _var_data=VarData(
                imports={"react": ["useEffect"]},
                hooks={"const [count, setCount] = useState(0);": use_count},
            ),
        )
        return [log_count]
```

The `useState` declaration renders before the `useEffect` that reads it, and both imports are included:

```javascript
export function Div_2b1c5f3e9a7d4c6e8f0a1b2c3d4e5f60() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    console.log(count);
  }, [count]);

  return jsx("div", {});
}
```

```md alert warning
# The `position` attribute of `VarData` and `Hooks.HookPosition` are deprecated.

Earlier versions sorted hooks into `PRE_TRIGGER` and `POST_TRIGGER` groups. Passing `position` now warns and has no effect on the order. To place a hook after another one, list the hook it reads in its `VarData(hooks=...)` as shown above.
```

```md alert info
# You can mix custom code and hooks in the same component. Hooks can access a variable defined in the custom code, but custom code cannot access a variable defined in a hook.
```

## Using a Hook's Return Value

`add_hooks` inserts hook statements into the component, but the values they define are not directly accessible from Python. When you need the return value of a no-argument hook, use `rx.vars.use_hook_var()`, which binds the hook call to a unique variable name and returns it as a `Var`. The hook statement and its import are automatically included in any component where the var is used, so it composes with regular props and var operations.

```python
import reflex as rx


def use_chart_width() -> rx.Var[int | None]:
    """Get the width of the enclosing recharts chart as a var."""
    return rx.vars.use_hook_var(
        library="recharts@3.8.1", hook="useChartWidth", _var_type=int | None
    )
```

For React's built-in [`useId`](https://react.dev/reference/react/useId), `rx.vars.use_id()` returns a `Var[str]` with a stable unique id for the component being rendered, e.g. for linking SVG elements to gradient or filter definitions.

A hook var is evaluated once per compiled component, so every element that reads it must render inside the same one. An `rx.el.svg` root, an `@rx.memo` body, and a custom renderer body each compile into a single component and satisfy this.
