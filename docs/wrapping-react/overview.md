```python exec
import reflex as rx
from typing import Any
from pcweb.components.spline import spline
from pcweb.templates.docpage import demo_box_style
from pcweb import constants
```

# Wrapping React Overview

One of Reflex's most powerful features is the ability to wrap React components. This allows us to build on top of the existing React ecosystem, and leverage the vast array of existing React components and libraries.

If you want a specific component for your app but Reflex doesn't provide it, there's a good chance it's available as a React component. Search for it on [npm]({constants.NPMJS_URL}), and if it's there, you can use it in your Reflex app.

In this section, we'll go over how to wrap React components on a high level. In the subsequent sections, we'll go over the details of how to wrap more complex components.

## Spline Example

Let's start with a library called [Spline]({constants.SPLINE_URL}). Spline is a tool for creating 3D scenes and animations. It's a great tool for creating interactive 3D visualizations.

We have some react code that creates a Spline scene. We want to wrap this code in a Reflex component so that we can use it in our Reflex app.

```javascript
import Spline from '@splinetool/react-spline';

export default function App() {
  return (
    <Spline scene="https://prod.spline.design/up1SQcRLq1s6yks3/scene.splinecode" />
  );
}
```

Here is how we would wrap this component in Reflex.

The two most important props are `library`, which is the name of the npm package, and `tag`, which is the name of the React component.

```python
class Spline(rx.Component):
    """Spline component."""

    library = "@splinetool/react-spline"
    tag = "Spline"
    scene: Var[str] = "https://prod.spline.design/Br2ec3WwuRGxEuij/scene.splinecode"
    is_default = True

    lib_dependencies: list[str] = ["@splinetool/runtime"]
```

Here the library is `@splinetool/react-spline` and the tag is `Spline`. In the next section we will go into a deep dive on imports but we also set `is_default = True` because the tag is the default export from the module.

Additionally, we can specify any props that the component takes. In this case, the `Spline` component takes a `scene` prop, which is the URL of the Spline scene.

## Full Example

```python eval
rx.center(
        spline(
            scene="https://prod.spline.design/joLpOOYbGL-10EJ4/scene.splinecode"
        ),
        overflow="hidden",
        width="100%",
        height="30em",
        padding="0",
        margin_bottom="1em",
        style=demo_box_style,
    )
```

```python
class Spline(rx.Component):
    """Spline component."""

    library = "@splinetool/react-spline"
    tag = "Spline"
    scene: Var[str] ="https://prod.spline.design/joLpOOYbGL-10EJ4/scene.splinecode"
    is_default = True

    lib_dependencies: list[str] = ["@splinetool/runtime"]

spline = Spline.create

def spline_example():
    return rx.center(
        spline(),
        overflow="hidden",
        width="100%",
        height="30em",
    )
```

## ColorPicker Example

Similar to the Spline example we start with defining the library and tag. In this case the library is `react-colorful` and the tag is `HexColorPicker`.

We also have a var `color` which is the current color of the color picker.

Since this component has interaction we must specify any event triggers that the component takes. The color picker has a single trigger `on_change` to specify when the color changes. This trigger takes in a single argument `color` which is the new color. Here `super().get_event_triggers()` is used to get the default event triggers for all components.

```python exec
class ColorPicker(rx.Component):
    library = "react-colorful"
    tag = "HexColorPicker"
    color: rx.Var[str]

    def get_event_triggers(self) -> dict[str, Any]:
        return {
            **super().get_event_triggers(),
            "on_change": lambda e0: [e0],
        }

color_picker = ColorPicker.create


class ColorPickerState(rx.State):
    color: str = "#db114b"
```

```python eval
rx.box(
        rx.vstack(
            rx.heading(ColorPickerState.color, color="white"),
            color_picker(
                on_change=ColorPickerState.set_color
            ),
        ),
        background_color=ColorPickerState.color,
        padding="5em",
        border_radius="1em",
        margin_bottom="1em",
    )
```

```python
class ColorPicker(rx.Component):
    library = "react-colorful"
    tag = "HexColorPicker"
    color: rx.Var[str]

    def get_event_triggers(self) -> dict[str, Any]:
        return \{
            **super().get_event_triggers(),
            "on_change": lambda e0: [e0],
        \}

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
