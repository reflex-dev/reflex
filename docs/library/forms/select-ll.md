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
---


```python exec
import random
import reflex as rx
import reflex.components.radix.primitives as rdxp
from pcweb.templates.docpage import style_grid
```

# Select

Displays a list of options for the user to pick from, triggered by a button.

## Basic Example

```python demo
rx.select.root(
    rx.select.trigger(),
    rx.select.content(
        rx.select.group(
            rx.select.label("Fruits"),
            rx.select.item("Orange", value="orange"),
            rx.select.item("Apple", value="apple"),
            rx.select.item("Grape", value="grape", disabled=True),
        ),
        rx.select.separator(),
        rx.select.group(
            rx.select.label("Vegetables"),
            rx.select.item("Carrot", value="carrot"),
            rx.select.item("Potato", value="potato"),
        ),
    ),
    default_value="apple",
)
```

## Usage

## Disabling

It is possible to disable individual items in a `select` using the `disabled` prop associated with the `rx.select.item`.

```python demo
rx.select.root(
    rx.select.trigger(placeholder="Select a Fruit"),
    rx.select.content(
        rx.select.group(
            rx.select.item("Apple", value="apple"),
            rx.select.item("Grape", value="grape", disabled=True),
            rx.select.item("Pineapple", value="pineapple"),
        ),
    ),
)
```

To prevent the user from interacting with select entirely, set the `disabled` prop to `True` on the `rx.select.root` component.

```python demo
rx.select.root(
    rx.select.trigger(placeholder="This is Disabled"),
    rx.select.content(
        rx.select.group(
            rx.select.item("Apple", value="apple"),
            rx.select.item("Grape", value="grape"),
        ),
    ),
    disabled=True,
)
```

## Setting Defaults

It is possible to set several default values when constructing a `select`.

The `placeholder` prop in the `rx.select.trigger` specifies the content that will be rendered when `value` or `default_value` is empty or not set.

```python demo
rx.select.root(
    rx.select.trigger(placeholder="pick a fruit"),
    rx.select.content(
        rx.select.group(
            rx.select.item("Apple", value="apple"),
            rx.select.item("Grape", value="grape"),
        ),
    ),
)
```

The `default_value` in the `rx.select.root` specifies the value of the `select` when initially rendered.
The `default_value` should correspond to the `value` of a child `rx.select.item`.

```python demo
rx.select.root(
    rx.select.trigger(),
    rx.select.content(
        rx.select.group(
            rx.select.item("Apple", value="apple"),
            rx.select.item("Grape", value="grape"),
        ),
    ),
    default_value="apple",
)
```

## Fully controlled

The `on_change` event trigger is fired when the value of the select changes.
In this example the `rx.select_root` `value` prop specifies which item is selected, and this
can also be controlled using state and a button without direct interaction with the select component.

```python demo exec
class SelectState2(rx.State):
    
    values: list[str] = ["apple", "grape", "pear"]
    
    value: str = ""

    def choose_randomly(self):
        """Change the select value var."""
        original_value = self.value
        while self.value == original_value:
            self.value = random.choice(self.values)


def select_example2():
    return rx.vstack(
        rx.select.root(
            rx.select.trigger(placeholder="No Selection"),
            rx.select.content(
                rx.select.group(
                    rx.foreach(SelectState2.values, lambda x: rx.select.item(x, value=x))
                ),
            ),
            value=SelectState2.value,
            on_change=SelectState2.set_value,
            
        ),
        rx.button("Choose Randomly", on_click=SelectState2.choose_randomly),
        rx.button("Reset", on_click=SelectState2.set_value("")),
    )
```

The `open` prop and `on_open_change` event trigger work similarly to `value` and `on_change` to control the open state of the select.
If `on_open_change` handler does not alter the `open` prop, the select will not be able to be opened or closed by clicking on the
`select_trigger`.

 ```python demo exec
class SelectState8(rx.State):
    is_open: bool = False
    
def select_example8():    
    return rx.flex(
        rx.select.root(
            rx.select.trigger(placeholder="No Selection"),
            rx.select.content(
                rx.select.group(
                    rx.select.item("Apple", value="apple"),
                    rx.select.item("Grape", value="grape"),
                ),
            ),
            open=SelectState8.is_open,
            on_open_change=SelectState8.set_is_open,
        ),
        rx.button("Toggle", on_click=SelectState8.set_is_open(~SelectState8.is_open)),
        spacing="2",
    )
```

### Submitting a Form with Select

When a select is part of a form, the `name` prop of the `rx.select.root` sets the key that will be submitted with the form data.

The `value` prop of `rx.select.item` provides the value to be associated with the `name` key when the form is submitted with that item selected.

When the `required` prop of the `rx.select.root` is `True`, it indicates that the user must select a value before the form may be submitted.

```python demo exec
class FormSelectState(rx.State):
    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_select():
    return rx.flex(
        rx.form.root(
            rx.flex(
                rx.select.root(
                    rx.select.trigger(),
                    rx.select.content(
                        rx.select.group(
                            rx.select.label("Fruits"),
                            rx.select.item("Orange", value="orange"),
                            rx.select.item("Apple", value="apple"),
                            rx.select.item("Grape", value="grape"),
                        ),
                        rx.select.separator(),
                        rx.select.group(
                            rx.select.label("Vegetables"),
                            rx.select.item("Carrot", value="carrot"),
                            rx.select.item("Potato", value="potato"),
                        ),
                    ),
                    default_value="apple",
                    name="select",
                ),
                rx.button("Submit"),
                width="100%",
                direction="column",
                spacing="2",
            ),
            on_submit=FormSelectState.handle_submit,
            reset_on_submit=True,
        ),
        rx.divider(size="4"),
        rx.heading("Results"),
        rx.text(FormSelectState.form_data.to_string()),
        width="100%",
        direction="column",
        spacing="2",
    )
```

## Real World Example

```python demo
rx.card(
    rx.flex(
        rx.image(src="/reflex_banner.png", width="100%", height="auto"),
        rx.flex(
            rx.heading("Reflex Swag", size="4", margin_bottom="4px"),
            rx.heading("$99", size="6", margin_bottom="4px"),
            direction="row", justify="between",
            width="100%",
        ),
        rx.text("Reflex swag with a sense of nostalgia, as if they carry whispered tales of past adventures", size="2", margin_bottom="4px"),
        rx.divider(size="4"),
        rx.flex(
            rx.flex(
                rx.text("Color", size="2", margin_bottom="4px", color_scheme="gray"),
                rx.select.root(
                    rx.select.trigger(),
                    rx.select.content(
                        rx.select.group(
                            rx.select.item("Light", value="light"),
                            rx.select.item("Dark", value="dark"),
                        ),
                    ),
                    default_value="light",
                ),
                direction="column",
            ),
            rx.flex(
                rx.text("Size", size="2", margin_bottom="4px", color_scheme="gray"),
                rx.select.root(
                    rx.select.trigger(),
                    rx.select.content(
                        rx.select.group(
                            rx.select.item("24", value="24"),
                            rx.select.item("26", value="26"),
                            rx.select.item("28", value="28", disabled=True),
                            rx.select.item("30", value="30"),
                            rx.select.item("32", value="32"),
                            rx.select.item("34", value="34"),
                            rx.select.item("36", value="36"),
                        ),
                    ),
                    default_value="30",
                ),
                direction="column",
            ),
            rx.button(rx.icon(tag="plus"), "Add"),
            align="end",
            justify="between",
            spacing="2",
            width="100%",
        ),
        width="15em",
        direction="column",
        spacing="2",
    ),
)
```
