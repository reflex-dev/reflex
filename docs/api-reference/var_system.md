# Reflex's Var System

## Motivation

Reflex supports some basic operations in state variables on the frontend.
Reflex automatically converts variable operations from Python into a JavaScript equivalent.

Here's an example of a Reflex conditional in Python that returns "Pass" if the threshold is equal to or greater than 50 and "Fail" otherwise:

```py
rx.cond(
    State.threshold >= 50,
    "Pass",
    "Fail",
)
```

The conditional to roughly the following in Javascript:

```js
state.threshold >= 50 ? "Pass" : "Fail";
```

## Overview

Simply put, a `Var` in Reflex represents a Javascript expression.
If the type is known, it can be any of the following:

- `NumberVar` represents an expression that evaluates to a Javascript `number`. `NumberVar` can support both integers and floating point values
- `BooleanVar` represents a boolean expression. For example: `false`, `3 > 2`.
- `StringVar` represents an expression that evaluates to a string. For example: `'hello'`, `(2).toString()`.
- `ArrayVar` represents an expression that evaluates to an array object. For example: `[1, 2, 3]`, `'words'.split()`.
- `ObjectVar` represents an expression that evaluates to an object. For example: `{a: 2, b: 3}`, `{deeply: {nested: {value: false}}}`.
- `NoneVar` represent null values. These can be either `undefined` or `null`.

## Creating Vars

State fields are converted to `Var` by default. Additionally, you can create a `Var` from Python values using `rx.Var.create()`:

```py
rx.Var.create(4)  # NumberVar
rx.Var.create("hello")  # StringVar
rx.Var.create([1, 2, 3])  # ArrayVar
```

If you want to explicitly create a `Var` from a raw Javascript string, you can instantiate `rx.Var` directly:

```py
rx.Var("2", _var_type=int).guess_type()  # NumberVar
```

In the example above, `.guess_type()` will attempt to downcast from a generic `Var` type into `NumberVar`.
For this example, calling the function `.to(int)` can also be used in place of `.guess_type()`.

## Operations

The `Var` system also supports some other basic operations.
For example, `NumberVar` supports basic arithmetic operations like `+` and `-`, as in Python.
It also supports comparisons that return a `BooleanVar`.

Custom `Var` operations can also be defined:

```py
from reflex.vars import var_operation, var_operation_return, ArrayVar, NumberVar


@var_operation
def multiply_array_values(a: ArrayVar):
    return var_operation_return(
        js_expression=f"{a}.reduce((p, c) => p * c, 1)",
        var_type=int,
    )


def factorial(value: NumberVar):
    return rx.cond(value <= 1, 1, multiply_array_values(rx.Var.range(1, value + 1)))
```

Use `js_expression` to pass explicit JavaScript expressions; in the `multiply_array_values` example, we pass in a JavaScript expression that calculates the product of all elements in an array called `a` by using the reduce method to multiply each element with the accumulated result, starting from an initial value of 1.
Later, we leverage `rx.cond` in the' factorial' function, we instantiate an array using the `range` function, and pass this array to `multiply_array_values`.

## Hook Vars

Some values only exist on the frontend and are exposed through React hooks.
`rx.vars.use_hook_var()` binds the return value of a hook to a unique variable name and returns it as a `Var`.
The hook call and the import of the hook are automatically included in any component that uses the var, so the value reflects the context of the component it is rendered in.

```py
chart_width = rx.vars.use_hook_var(
    library="recharts@3.8.1",
    hook="useChartWidth",
    _var_type=int | None,
)
```

A component using `chart_width` will import `useChartWidth` from `recharts` and render `const <unique_name> = useChartWidth();` in its body, so `chart_width` can be used like any other `Var[int | None]`.

Any positional arguments are passed to the hook call:

```py
theme = rx.vars.use_hook_var("react", "useContext", theme_context, _var_type=str)
```

### Binding Values with `const`

`use_hook_var()` is a thin wrapper over `rx.vars.const()`, which binds any value to a `const` declaration in the component's hook scope and returns a `Var` referring to the bound name.
Use it directly to name an expression, or to bind a hook built with `rx.vars.hook_fn()`:

```py
use_dropzone = rx.vars.hook_fn("react-dropzone", "useDropzone")
dropzone = rx.vars.const(use_dropzone.call(options), name="dropzone")
```

`hook_fn()` imports the hook under its own name; pass `alias` to import it under a different one, which is needed when the same hook name may reach one component from more than one library.
`use_hook_var()` always aliases, since its caller does not control which other hooks reach the components its var ends up in.

By default each call binds to a fresh unique name.
Passing `name` uses that identifier verbatim, which also means two calls with the same name and value produce the same declaration and are emitted only once.

### Destructuring

`rx.vars.const_unpack()` and `rx.vars.const_fields()` bind several values from one hook call by destructuring it, so the hook runs once no matter how many of its values are used.

`const_unpack()` destructures an array, typing each binding by its index:

```py
use_state = rx.vars.hook_fn("react", "useState", returns=tuple[int, Callable])
count, set_count = rx.vars.const_unpack(use_state.call(0), 2)
# const [<count>, <set_count>] = useState(0);
```

Pass `names` to choose the identifiers, using `None` to skip a position; a skipped position returns no `Var`.
Pass `rest` to bind the remaining elements, which is returned last:

```py
(set_count,) = rx.vars.const_unpack(use_state.call(0), 2, names=(None, "setCount"))
# const [, setCount] = useState(0);
```

`const_fields()` destructures an object by field name, typing each binding by that field:

```py
root_props, is_drag_active = rx.vars.const_fields(
    use_dropzone.call(options), "getRootProps", "isDragActive"
)
# const { getRootProps: <root_props>, isDragActive: <is_drag_active> } = useDropzone(options);
```

When the value is typed as a `TypedDict` or dataclass, each binding gets that field's declared type and an unknown field name raises.
Binding a field to its own name renders the JavaScript shorthand, and `rest` binds the remaining fields:

```py
app_id, other_options = rx.vars.const_fields(
    options, "appId", names=("appId",), rest="otherOptions"
)
# const { appId, ...otherOptions } = <options>;
```

A hook var is evaluated once per compiled component, so every element that reads it must render inside the same one. An `rx.el.svg` root, an `@rx.memo` body, and a custom renderer body each compile into a single component and satisfy this.

For the common case of React's built-in [`useId`](https://react.dev/reference/react/useId), `rx.vars.use_id()` returns a `Var[str]` containing a stable unique id for the rendered component.
This is useful for linking SVG elements to `defs` such as gradients or filters:

```py
def gradient_rect() -> rx.Component:
    gradient_id = rx.vars.use_id()
    return rx.el.svg(
        rx.el.svg.linear_gradient(
            rx.el.svg.stop(offset="0%", stop_color="gold"),
            rx.el.svg.stop(offset="100%", stop_color="tomato"),
            id=gradient_id,
        ),
        rx.el.svg.rect(fill=f"url(#{gradient_id})", width=64, height=64),
        width=64,
        height=64,
    )
```
