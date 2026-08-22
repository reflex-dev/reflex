```python exec
import reflex as rx
from typing import Any
```

# Wrapping React

One of Reflex's most powerful features is the ability to wrap React components and take advantage of the vast ecosystem of React libraries.

If you want a specific component for your app but Reflex doesn't provide it, there's a good chance it's available as a React component. Search for it on [npm](https://www.npmjs.com/), and if it's there, you can use it in your Reflex app. You can also create your own local React components and wrap them in Reflex.

Once you wrap your component, you [publish it](/docs/custom-components/overview) to the Reflex library so that others can use it.

## Simple Example

Simple components that don't have any interaction can be wrapped with just a few lines of code.

Below we show how to wrap the [Spline](https://github.com/splinetool/react-spline) library can be used to create 3D scenes and animations.

```python demo exec
import reflex as rx


class Spline(rx.Component):
    """Spline component."""

    # The name of the npm package.
    library = "@splinetool/react-spline@4.1.0"

    # Any additional libraries needed to use the component.
    lib_dependencies: list[str] = ["@splinetool/runtime@1.5.5"]

    # The name of the component to use from the package.
    tag = "Spline"

    # Spline is a default export from the module.
    is_default = True

    # Any props that the component takes.
    scene: rx.Var[str]


# Convenience function to create the Spline component.
spline = Spline.create


# Use the Spline component in your app.
def index():
    return spline(scene="https://prod.spline.design/joLpOOYbGL-10EJ4/scene.splinecode")
```

## ColorPicker Example

Similar to the Spline example we start with defining the library and tag. In this case the library is `react-colorful` and the tag is `HexColorPicker`.

We also have a var `color` which is the current color of the color picker.

Since this component has interaction we must specify any event triggers that the component takes. The color picker has a single trigger `on_change` to specify when the color changes. This trigger takes in a single argument `color` which is the new color.

```python exec
from reflex.components.component import NoSSRComponent


class ColorPicker(NoSSRComponent):
    library = "react-colorful@5.7.0"
    tag = "HexColorPicker"
    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]


color_picker = ColorPicker.create

ColorPickerState = rx.client_state("#db114b", name="color")
```

```python eval
rx.box(
    ColorPickerState,
    rx.vstack(
        rx.heading(ColorPickerState.value, as_="h2", color="white"),
        color_picker(on_change=ColorPickerState.set),
    ),
    background_color=ColorPickerState.value,
    padding="5em",
    border_radius="12px",
    margin_bottom="1em",
)
```

```python
from reflex.components.component import NoSSRComponent


class ColorPicker(NoSSRComponent):
    library = "react-colorful@5.7.0"
    tag = "HexColorPicker"
    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]


color_picker = ColorPicker.create


class ColorPickerState(rx.State):
    color: str = "#db114b"

    @rx.event
    def set_color(self, value: str):
        self.color = value


def index():
    return rx.box(
        rx.vstack(
            rx.heading(ColorPickerState.color, as_="h2", color="white"),
            color_picker(on_change=ColorPickerState.set_color),
        ),
        background_color=ColorPickerState.color,
        padding="5em",
        border_radius="1em",
    )
```

## Naming And Scoping Client State

Whether a client state var is shared app-wide follows from whether you name it:

```python
shared = rx.client_state(
    "", name="search_query"
)  # global: any component, and the backend
private = rx.client_state("")  # scoped to the component tree using it
```

A **named** var resolves in one app-wide store, so any component can read and write it and
`push`, `retrieve`, `global_value` and `global_set` all work against it.

An **unnamed** var gets a compile-time name and is scoped: the first component in a tree to
use it claims it for that tree, so each instance of that component gets its own state, the
way React's `useState` does. Nothing outside the tree can address it.

Where you *construct* the var decides who shares it. Construct it inside a component and
each instance gets its own:

```python
@rx.memo
def copy_button(text: rx.Var[str]) -> rx.Component:
    copied = rx.client_state(False)  # one per rendered button
    ...
```

Construct it once at module level and reference it from several components and they share
it, owned by the outermost one that uses it — the same way lifting state up works in React.
Note the consequence: adding a read at page level makes the page the owner, which collapses
per-instance state below it into one shared value.

A plain helper function called several times gives each call its own state for free, since
the var is constructed once per call:

```python
def counter():
    count = rx.client_state(0)  # a distinct var per call
    return rx.hstack(
        rx.button("-", on_click=count.set(lambda v: v - 1)),
        rx.heading(count.value),
        rx.button("+", on_click=count.set(lambda v: v + 1)),
    )


rx.vstack(counter(), counter(), counter())  # three independent counters
```

Each item rendered by `rx.foreach` is its own scope too, so an unnamed var used in a
loop body is per item, and can be seeded from the loop item or index:

```python
def row(item: rx.Var[str], index: rx.Var[int]) -> rx.Component:
    expanded = rx.client_state(False)  # one per rendered row
    count = rx.client_state(index)  # row N starts at N
    ...


rx.foreach(State.items, row)
```

A default is read once, when the scope first claims the name, so it seeds the state
rather than tracking the var. Set the value explicitly (`on_mount=count.set(index)`)
when you need it to follow.

Pass `prefix=` to make generated names readable in the compiled output:
`rx.client_state(0, prefix="counter")`.

## Setting Client State From Plain JavaScript

`value` and `set` are the normal way to use a client state var, but they resolve to a
hook, so they only work inside a component that Reflex renders. When you are wrapping a
library that hands you a plain JavaScript callback -- or you are writing your own JS in
`add_custom_code` -- use `global_value` and `global_set` instead. They need no hook, so
they work anywhere in your compiled page:

```python
picker_color = rx.client_state("#db114b", name="picker_color")


class MyPicker(rx.Component):
    library = "some-non-react-picker"
    tag = "Picker"

    def add_custom_code(self) -> list[str]:
        # `global_set` is a plain function, so a non-React callback can call it.
        return [f"const onPickerChange = {picker_color.global_set};"]
```

Reads through `global_value` are a point-in-time snapshot with no reactivity, so prefer
`value` inside components. Writes through `global_set` re-render every component
subscribed to that var, exactly like `set` does. Both require a **named** client state
var, since the name is what identifies the value.

`rx.call_script` is the one place these do not work: its code is evaluated inside the
Reflex runtime module, so your page's imports are not in scope there. Reach the store
through the `refs` object instead, which is also how you inspect client state from the
browser devtools console:

```python
rx.call_script('refs["__client_state"].set("picker_color", "#ffffff")')
```

## What Not To Wrap

There are some libraries on npm that are not do not expose React components and therefore are very hard to wrap with Reflex.

A library like [spline](https://www.npmjs.com/package/@splinetool/runtime) below is going to be difficult to wrap with Reflex because it does not expose a React component.

```javascript
import { Application } from '@splinetool/runtime';

// make sure you have a canvas in the body
const canvas = document.getElementById('canvas3d');

// start the application and load the scene
const spline = new Application(canvas);
spline.load('https://prod.spline.design/6Wq1Q7YGyM-iab9i/scene.splinecode');
```

You should look out for JSX, a syntax extension to JavaScript, which has angle brackets `(<h1>Hello, world!</h1>)`. If you see JSX, it's likely that the library is a React component and can be wrapped with Reflex.

If the library does not expose a react component you need to try and find a JS React wrapper for the library, such as [react-spline](https://www.npmjs.com/package/@splinetool/react-spline).

```javascript
import Spline from "@splinetool/react-spline";

export default function App() {
  return (
    <div>
      <Spline scene="https://prod.spline.design/6Wq1Q7YGyM-iab9i/scene.splinecode" />
    </div>
  );
}
```

In the next page, we will go step by step through a more complex example of wrapping a React component.
