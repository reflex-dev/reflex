```python exec
import reflex as rx
```

# Conditional Rendering

Recall from the [basics](/docs/getting-started/basics/) that we cannot use Python `if/else` statements when referencing state vars in Reflex. Instead, use the `rx.cond` component to conditionally render components or set props based on the value of a state var.

```md video https://youtube.com/embed/ITOZkzjtjUA?start=6040&end=6463
# Video: Conditional Rendering
```

```md alert
# Check out the API reference for [cond docs](/docs/library/dynamic-rendering/cond/).
```

```python eval notest
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

```python test
def test_cond_toggles_text(demo):
    expect(demo.get_by_text("Text 1")).to_be_visible()
    demo.get_by_role("button", name="Toggle").click()
    expect(demo.get_by_text("Text 2")).to_be_visible()
    expect(demo.get_by_text("Text 1")).to_be_hidden()
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

```python test
def test_cond_prop_changes_color_scheme(demo):
    slider = demo.locator(".rt-SliderRoot")
    expect(slider).to_have_attribute("data-accent-color", "pink")
    demo.get_by_role("slider").press("ArrowRight")
    expect(slider).to_have_attribute("data-accent-color", "green")
```

## Var Operations

You can use [var operations](/docs/vars/var-operations/) with the `cond` component for more complex conditions. See the full [cond reference](/docs/library/dynamic-rendering/cond/) for more details.

## Multiple Conditional Statements

The [`rx.match`](/docs/library/dynamic-rendering/match/) component in Reflex provides a powerful alternative to`rx.cond` for handling multiple conditional statements and structural pattern matching. This component allows you to handle multiple conditions and their associated components in a cleaner and more readable way compared to nested `rx.cond` structures.

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

```python test
def test_match_shows_breed_text(demo, page):
    expect(demo.get_by_text("Unknown cat breed selected.")).to_be_visible()
    demo.get_by_role("combobox").click()
    page.get_by_role("option", name="siamese").click()
    expect(demo.get_by_text("Siamese cat selected.")).to_be_visible()
    demo.get_by_role("combobox").click()
    page.get_by_role("option", name="pug").click()
    expect(demo.get_by_text("Unknown cat breed selected.")).to_be_visible()
```
