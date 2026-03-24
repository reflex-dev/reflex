```python exec
import reflex as rx
from pcweb.pages.docs.library import library
from pcweb.pages import docs
```

# Props

Props modify the behavior and appearance of a component. They are passed in as keyword arguments to a component.

## Component Props

There are props that are shared between all components, but each component can also define its own props.

For example, the `rx.image` component has a `src` prop that specifies the URL of the image to display and an `alt` prop that specifies the alternate text for the image.

```python demo
rx.image(
    src="https://web.reflex-assets.dev/other/logo.jpg",
    alt="Reflex Logo",
)
```

Check the docs for the component you are using to see what props are available and how they affect the component (see the `rx.image` [reference]({docs.library.media.image.path}#api-reference) page for example).


## Common Props

Components support many standard HTML properties as props. For example: the HTML [id]({"https://www.w3schools.com/html/html_id.asp"}) property is exposed directly as the prop `id`. The HTML [className]({"https://www.w3schools.com/jsref/prop_html_classname.asp"}) property is exposed as the prop `class_name` (note the Pythonic snake_casing!).

```python demo
rx.box(
    "Hello World",
    id="box-id",
    class_name=["class-name-1", "class-name-2",],
)
```

In the example above, the `class_name` prop of the `rx.box` component is assigned a list of class names. This means the `rx.box` component will be styled with the CSS classes `class-name-1` and `class-name-2`.

## Style Props

In addition to component-specific props, most built-in components support a full range of style props. You can use any [CSS property](https://www.w3schools.com/cssref/index.php) to style a component.

```python demo
rx.button(
    "Fancy Button",
    border_radius="1em",
    box_shadow="rgba(151, 65, 252, 0.8) 0 15px 30px -10px",
    background_image="linear-gradient(144deg,#AF40FF,#5B42F3 50%,#00DDEB)",
    box_sizing="border-box",
    color="white",
    opacity= 1,
)
```

See the [styling docs]({docs.styling.overview.path}) to learn more about customizing the appearance of your app.


## Binding Props to State

```md alert warning
# Optional: Learn all about [State]({docs.state.overview.path}) first.
```

Reflex apps define [State]({docs.state.overview.path}) classes that hold variables that can change over time.

State may be modified in response to things like user input like clicking a button, or in response to events like loading a page.

State vars can be bound to component props, so that the UI always reflects the current state of the app.

Try clicking the badge below to change its color.

```python demo exec
class PropExampleState(rx.State):
    text: str = "Hello World"
    color: str = "red"

    @rx.event
    def flip_color(self):
        if self.color == "red":
            self.color = "blue"
        else:
            self.color = "red"


def index():
    return rx.button(
        PropExampleState.text,
        color_scheme=PropExampleState.color,
        on_click=PropExampleState.flip_color,
    )
```

In this example, the `color_scheme` prop is bound to the `color` state var.

When the `flip_color` event handler is called, the `color` var is updated, and the `color_scheme` prop is updated to match.
