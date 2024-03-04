```python exec
from pcweb.pages.docs.library import library
from pcweb.pages.docs import state, vars
import reflex as rx
```

# Props

Props modify the behavior and appearance of a component. They are passed in as keyword arguments to the component function.

## Component Props

Each component has props that are specific to that component. For example, the `rx.avatar` component has a fallback prop that sets the `fallback` of the avatar.

```python demo
rx.avatar(
    fallback="JD"
)
```

Check the docs for the component you are using to see what props are available.

```md alert success
# Reflex has a wide selection of [built-in components]({library.path}) to get you started quickly.
```

## HTML Props

Components support many standard HTML properties as props. For example: the HTML [id]({"https://www.w3schools.com/html/html_id.asp"}) property is exposed directly as the prop `id`. The HTML [className]({"https://www.w3schools.com/jsref/prop_html_classname.asp"}) property is exposed as the prop `class_name` (note the Pythonic snake_casing!).

```python demo
rx.box(
    "Hello World",
    id="box-id",
    class_name=["class-name-1", "class-name-2",],
)
```

## Binding Props to State

Reflex apps can have a [State]({state.overview.path}) that stores all variables that can change when the app is running, as well as the event handlers that can change those variables.

State may be modified in response to things like user input like clicking a button, or in response to events like loading a page.

State vars can be bound to component props, so that the UI always reflects the current state of the app.

```md alert warning
Optional: Learn all about [State]({state.overview.path}) first.
```

You can set the value of a prop to a [state var]({vars.base_vars.path}) to make the component update when the var changes.

Try clicking the badge below to change its color.

```python demo exec
class PropExampleState(rx.State):
    text: str = "Hello World"
    color: str = "red"

    def flip_color(self):
        if self.color == "red":
            self.color = "blue"
        else:
            self.color = "red"


def index():
    return rx.badge(
        PropExampleState.text,
        color_scheme=PropExampleState.color,
        on_click=PropExampleState.flip_color,
        font_size="1.5em",
        _hover={
            "cursor": "pointer",
        }
    )
```

In this example, the `color_scheme` prop is bound to the `color` state var.

When the `flip_color` event handler is called, the `color` var is updated, and the `color_scheme` prop is updated to match.
