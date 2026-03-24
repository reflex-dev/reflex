```python exec
import reflex as rx
from typing import Any
from pcweb.components.spline import spline
from pcweb.pages.docs import custom_components
from pcweb import constants
```

# Wrapping React

One of Reflex's most powerful features is the ability to wrap React components and take advantage of the vast ecosystem of React libraries.

If you want a specific component for your app but Reflex doesn't provide it, there's a good chance it's available as a React component. Search for it on [npm]({constants.NPMJS_URL}), and if it's there, you can use it in your Reflex app. You can also create your own local React components and wrap them in Reflex.

Once you wrap your component, you [publish it]({custom_components.overview.path}) to the Reflex library so that others can use it.

## Simple Example

Simple components that don't have any interaction can be wrapped with just a few lines of code. 

Below we show how to wrap the [Spline]({constants.SPLINE_URL}) library can be used to create 3D scenes and animations.

```python demo exec
import reflex as rx

class Spline(rx.Component):
    """Spline component."""

    # The name of the npm package.
    library = "@splinetool/react-spline"

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
    library = "react-colorful"
    tag = "HexColorPicker"
    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]

color_picker = ColorPicker.create

ColorPickerState = rx._x.client_state(default="#db114b", var_name="color")
```

```python eval
rx.box(
    ColorPickerState,
    rx.vstack(
        rx.heading(ColorPickerState.value, color="white"),
        color_picker(
            on_change=ColorPickerState.set_value
        ),
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
    library = "react-colorful"
    tag = "HexColorPicker"
    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]

color_picker = ColorPicker.create

class ColorPickerState(rx.State):
    color: str = "#db114b"

def index():
    return rx.box(
        rx.vstack(
            rx.heading(ColorPickerState.color, color="white"),
            color_picker(
                on_change=ColorPickerState.set_color
            ),
        ),
        background_color=ColorPickerState.color,
        padding="5em",
        border_radius="1em",
    )
```

## What Not To Wrap

There are some libraries on npm that are not do not expose React components and therefore are very hard to wrap with Reflex. 

A library like [spline](https://www.npmjs.com/package/@splinetool/runtime) below is going to be difficult to wrap with Reflex because it does not expose a React component.

```javascript
import \{ Application } from '@splinetool/runtime';

// make sure you have a canvas in the body
const canvas = document.getElementById('canvas3d');

// start the application and load the scene
const spline = new Application(canvas);
spline.load('https://prod.spline.design/6Wq1Q7YGyM-iab9i/scene.splinecode');
```

You should look out for JSX, a syntax extension to JavaScript, which has angle brackets `(<h1>Hello, world!</h1>)`. If you see JSX, it's likely that the library is a React component and can be wrapped with Reflex. 

If the library does not expose a react component you need to try and find a JS React wrapper for the library, such as [react-spline](https://www.npmjs.com/package/@splinetool/react-spline).

```javascript
import Spline from '@splinetool/react-spline';

export default function App() {
  return (
    <div>
      <Spline scene="https://prod.spline.design/6Wq1Q7YGyM-iab9i/scene.splinecode" />
    </div>
  );
}
```



In the next page, we will go step by step through a more complex example of wrapping a React component.
