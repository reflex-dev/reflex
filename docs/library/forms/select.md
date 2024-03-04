---
components:
    - rx.radix.select
    - rx.radix.select.root
    - rx.radix.select.trigger
    - rx.radix.select.content
    - rx.radix.select.group
    - rx.radix.select.item
    - rx.radix.select.label
    - rx.radix.select.separator

HighLevelSelect: |
    lambda **props: rx.radix.themes.select(["apple", "grape", "pear"], default_value="pear", **props)

SelectRoot: |
    lambda **props: rx.radix.themes.select.root(
        rx.radix.themes.select.trigger(),
        rx.radix.themes.select.content(
            rx.radix.themes.select.group(
                rx.radix.themes.select.item("apple", value="apple"),
                rx.radix.themes.select.item("grape", value="grape"),
                rx.radix.themes.select.item("pear", value="pear"),
            ),
        ),
        default_value="pear",
        **props
    )

SelectTrigger: |
    lambda **props: rx.radix.themes.select.root(
        rx.radix.themes.select.trigger(**props),
        rx.radix.themes.select.content(
            rx.radix.themes.select.group(
                rx.radix.themes.select.item("apple", value="apple"),
                rx.radix.themes.select.item("grape", value="grape"),
                rx.radix.themes.select.item("pear", value="pear"),
            ),
        ),
        default_value="pear",
    )

SelectContent: |
    lambda **props: rx.radix.themes.select.root(
        rx.radix.themes.select.trigger(),
        rx.radix.themes.select.content(
            rx.radix.themes.select.group(
                rx.radix.themes.select.item("apple", value="apple"),
                rx.radix.themes.select.item("grape", value="grape"),
                rx.radix.themes.select.item("pear", value="pear"),
            ),
            **props,
        ),
        default_value="pear",
    )

SelectItem: |
    lambda **props: rx.radix.themes.select.root(
        rx.radix.themes.select.trigger(),
        rx.radix.themes.select.content(
            rx.radix.themes.select.group(
                rx.radix.themes.select.item("apple", value="apple", **props),
                rx.radix.themes.select.item("grape", value="grape"),
                rx.radix.themes.select.item("pear", value="pear"),
            ),
        ),
        default_value="pear",
    )
---


```python exec
import random
import reflex as rx
from pcweb.templates.docpage import style_grid
```

# High Level Select

Displays a list of options for the user to pick from—triggered by a button.

## Basic Example

```python demo
rx.select(["Apple", "Orange", "Banana", "Grape", "Pear"])
```

## Disabling

To prevent the user from interacting with select, set the `disabled` prop to `True`.

```python demo
rx.select(["Apple", "Orange", "Banana", "Grape", "Pear"], disabled=True)
```

## Setting Defaults

It is possible to set several default values when constructing a `select`.

Can set the `placeholder` prop, which is the content that will be rendered when no value or no default_value is set.

Can set the `label` prop, which is a label in the `select`.

```python demo
rx.select(["Apple", "Orange", "Banana", "Grape", "Pear"], placeholder="Selection of Fruits", label="Fruits")
```

Can set the `default_value` prop, which is the value of the `select` when initially rendered.

```python demo
rx.select(["Apple", "Orange", "Banana", "Grape", "Pear"], default_value="Orange")
```

## Simple Styling

Can set the `color`, `variant` and `radius` to easily style the `select`.

```python demo
rx.select(["Apple", "Orange", "Banana", "Grape", "Pear"], color="pink", variant="soft", radius="full", width="100%")
```

## High control of select component (value and open changes)

The `on_change` event is called when the value of the `select` changes. In this example we set the `value` prop to change the select `value` using a button in this case.

```python demo exec
class SelectState3(rx.State):
    
    values: list[str] = ["apple", "grape", "pear"]
    
    value: str = "apple"

    def change_value(self):
        """Change the select value var."""
        self.value = random.choice(self.values)


def select_example3():
    return rx.vstack(
        rx.select(
            SelectState3.values,
            value=SelectState3.value,
            on_change=SelectState3.set_value,
        ),
        rx.button("Change Value", on_click=SelectState3.change_value),
        
    )
```

The `on_open_change` event handler acts in a similar way to the `on_change` and is called when the open state of the select changes.

```python demo
rx.select(
    ["apple", "grape", "pear"],
    on_change=rx.window_alert("on_change event handler called"),
)

```

### Submitting a form using select

The `name` prop is needed to submit with its owning form as part of a name/value pair.

When the `required` prop is `True`, it indicates that the user must select a value before the owning form can be submitted.

```python demo exec
class FormSelectState1(rx.State):
    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_select1():
    return rx.vstack(
        rx.form.root(
            rx.vstack(
                rx.select(
                    ["apple", "grape", "pear"],
                    default_value="apple",
                    name="select",
                ),
                rx.button("Submit", type="submit"),
                width="100%",
            ),
            on_submit=FormSelectState1.handle_submit,
            reset_on_submit=True,
            width="100%",
        ),
        rx.divider(width="100%"),
        rx.heading("Results"),
        rx.text(FormSelectState1.form_data.to_string()),
        width="100%",
    )
```

## Real World Example

```python demo
rx.card(
    rx.vstack(
        rx.image(src="/reflex_banner.png", width="100%", height="auto"),
        rx.flex(
            rx.heading("Reflex Swag", size="4", mb="1"),
            rx.heading("$99", size="6", mb="1"),
            direction="row", justify="between",
            width="100%",
        ),
        rx.text("Reflex swag with a sense of nostalgia, as if they carry whispered tales of past adventures", size="2", mb="1"),
        rx.divider(width="100%"),
        rx.flex(
            rx.flex(
                rx.text("Color", size="2", mb="1", color_scheme="gray"),
                rx.select(["light", "dark"], default_value="light"),
                direction="column",
            ),
            rx.flex(
                rx.text("Size", size="2", mb="1", color_scheme="gray"),
                rx.select(["24", "26", "28", "30", "32", "34", "36"], default_value="30"),
                direction="column",
            ),
            rx.flex(
                rx.text(".", size="2",),
                rx.button("Add to cart"),
                direction="column",
            ),
            direction="row",
            justify="between",
            width="100%",
        ),
        width="20vw",
    ),
)
```
