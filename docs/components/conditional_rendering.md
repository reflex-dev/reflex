```python exec
import reflex as rx

from pcweb.pages.docs import library
from pcweb.pages import docs
```

# Conditional Rendering

Recall from the [basics]({docs.getting_started.basics.path}) that we cannot use Python `if/else` statements when referencing state vars in Reflex. Instead, use the `rx.cond` component to conditionally render components or set props based on the value of a state var.

```md video https://youtube.com/embed/ITOZkzjtjUA?start=6040&end=6463
# Video: Conditional Rendering
```

```md alert
# Check out the API reference for [cond docs]({library.dynamic_rendering.cond.path}).
```

```python eval
rx.box(height="2em")
```

Below is a simple example showing how to toggle between two text components by checking the value of the state var `show`.

```python demo exec
class CondSimpleState(rx.State):
    show: bool = True

    @rx.event
    def change(self):
        self.show = not (self.show)


def cond_simple_example():
    return rx.vstack(
        rx.button("Toggle", on_click=CondSimpleState.change),
        rx.cond(
            CondSimpleState.show,
            rx.text("Text 1", color="blue"),
            rx.text("Text 2", color="red"),
        ),
    )
```

If `show` is `True` then the first component is rendered (in this case the blue text). Otherwise the second component is rendered (in this case the red text).

## Conditional Props

You can also set props conditionally using `rx.cond`. In this example, we set the `color` prop of a text component based on the value of the state var `show`.

```python demo exec
class PropCondState(rx.State):

    value: int

    @rx.event
    def set_end(self, value: list[int | float]):
        self.value = value[0]


def cond_prop():
    return rx.slider(
        default_value=[50],
        on_value_commit=PropCondState.set_end,
        color_scheme=rx.cond(PropCondState.value > 50, "green", "pink"),
        width="100%",
    )
```


## Var Operations

You can use [var operations]({docs.vars.var_operations.path}) with the `cond` component for more complex conditions. See the full [cond reference]({library.dynamic_rendering.cond.path}) for more details.


## Multiple Conditional Statements

The [`rx.match`]({library.dynamic_rendering.match.path}) component in Reflex provides a powerful alternative to`rx.cond` for handling multiple conditional statements and structural pattern matching. This component allows you to handle multiple conditions and their associated components in a cleaner and more readable way compared to nested `rx.cond` structures.

```python demo exec
from typing import List

import reflex as rx


class MatchState(rx.State):
    cat_breed: str = ""
    animal_options: List[str] = [
        "persian",
        "siamese",
        "maine coon",
        "ragdoll",
        "pug",
        "corgi",
    ]

    @rx.event
    def set_cat_breed(self, breed: str):
        self.cat_breed = breed


def match_demo():
    return rx.flex(
        rx.match(
            MatchState.cat_breed,
            ("persian", rx.text("Persian cat selected.")),
            ("siamese", rx.text("Siamese cat selected.")),
            (
                "maine coon",
                rx.text("Maine Coon cat selected."),
            ),
            ("ragdoll", rx.text("Ragdoll cat selected.")),
            rx.text("Unknown cat breed selected."),
        ),
        rx.select(
            [
                "persian",
                "siamese",
                "maine coon",
                "ragdoll",
                "pug",
                "corgi",
            ],
            value=MatchState.cat_breed,
            on_change=MatchState.set_cat_breed,
        ),
        direction="column",
        gap="2",
    )
```
