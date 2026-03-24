
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
- More complex hooks that need to have special import or be written in a specific order can be added as `rx.Var` with a `VarData` object to specify the position of the hook.
    - The `imports` attribute of the `VarData` object can be used to specify any imports that need to be included in the component.
    - The `position` attribute of the `VarData` object can be set to `Hooks.HookPosition.PRE_TRIGGER` or `Hooks.HookPosition.POST_TRIGGER` to specify the position of the hook in the component.

```md alert info
# The `position` attribute is only used for hooks that need to be written in a specific order. 
- If an event handler need to refer to a variable defined in a hook, the hook should be written before the event handler.
- If a hook need to refer to the memoized event handler by name, the hook should be written after the event handler.
```

```python
from reflex.vars.base import Var, VarData
from reflex.constants import Hooks
from reflex.components.el.elements import Div

class ComponentWithHooks(Div, MyBaseComponent):
    """MyComponent."""

    def add_hooks(self) -> list[str| Var]:
        """Add hooks to the component."""
        hooks = []
        hooks1 = """const customHookVariable = "some value";"""
        hooks.append(hooks1)

        # A hook that need to be written before the memoized event handlers.
        hooks2 = Var(
            """useEffect(() => {
                console.log("PreTrigger: " + customHookVariable);
            }, []);
            """,
            _var_data=VarData(
                imports=\{"react": ["useEffect"],\},
                position=Hooks.HookPosition.PRE_TRIGGER
            ),
        )
        hooks.append(hooks2)

        hooks3 = Var(
            """useEffect(() => {
                console.log("PostTrigger: " + customHookVariable);
            }, []);
            """,
            _var_data=VarData(
                imports=\{"react": ["useEffect"],\},
                position=Hooks.HookPosition.POST_TRIGGER
            ),
        )
        hooks.append(hooks3)
        return hooks
```

The `ComponentWithHooks` will be rendered in the component in the following way:

```javascript
export function Div_7178f430b7b371af8a12d8265d65ab9b() {
  const customHookVariable = "some value";

  useEffect(() => {
    console.log("PreTrigger: " + customHookVariable);
  }, []);

  /* memoized triggers such as on_click, on_change, etc will render here */

  useEffect(() => {
    console.log("PostTrigger: "+ customHookVariable);
  }, []);

  return jsx("div", \{\});
}
```

```md alert info
# You can mix custom code and hooks in the same component. Hooks can access a variable defined in the custom code, but custom code cannot access a variable defined in a hook.
```
