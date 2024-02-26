---
components:
    - rx.radix.radio_group
    - rx.radix.radio_group.root
    - rx.radix.radio_group.item
---


```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
```

# Radio Group

A set of interactive radio buttons where only one can be selected at a time.

## Basic example

The `rx.radio.root` contains all the parts of a radio group. The `rx.radio.item` is an item in the group that can be checked.

```python demo
rx.radio.root(
    rx.radio.item(value="1"),
    rx.radio.item(value="2"),
    rx.radio.item(value="3"),
    default_value="1",
)

```

The `default_value` prop is used to set the value of the radio item that should be checked when initially rendered.

## Radio Group Root

### Control the value

The state can specify which item in a radio group is checked by setting the `value` prop,
making the radio group a fully-controlled input. To allow the user to change the selected
value by clicking, the `on_change` event handler must be defined to update
the Var representing the current `value`.

```python demo exec
class RadioState1(rx.State):
    val: str = ""
    
    @rx.cached_var
    def display_value(self):
        return self.val or "No Selection"


def radio_state_example():
    return rx.flex(
        rx.badge(
            RadioState1.display_value,
            color_scheme="green"
        ),
        rx.radio.root(
            rx.radio.item(value="1"),
            rx.radio.item(value="2"),
            rx.radio.item(value="3"),
            value=RadioState1.val,
            on_change=RadioState1.set_val,
        ),
        rx.button("Clear", on_click=RadioState1.set_val("")),
        align="center",
        justify="center",
        direction="column",
        spacing="2",
    )
```

When the `disabled` prop is set to `True`, it prevents the user from interacting with radio items.

```python demo
rx.flex(
    rx.radio.root(
        rx.radio.item(value="1"),
        rx.radio.item(value="2"),
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        rx.radio.item(value="2"),
        disabled=True,
    ),
    spacing="2",
)

```

### Submitting a form using Radio Group

The `name` prop is used to name the group. It is submitted with its owning form as part of a name/value pair.

When the `required` prop is `True`, it indicates that the user must check a radio item before the owning form can be submitted.

```python demo exec
class FormRadioState(rx.State):
    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_example():
    return rx.flex(
        rx.form.root(
            rx.flex(
                rx.radio.root(
                    "Radio Group ",
                    rx.radio.item(value="1"),
                    rx.radio.item(value="2"),
                    rx.radio.item(value="3"),
                    name="radio",
                    required=True,
                ),
                rx.button("Submit", type="submit"),
                direction="column",
                spacing="2",
            ),
            on_submit=FormRadioState.handle_submit,
            reset_on_submit=True,
        ),
        rx.divider(size="4"),
        rx.heading("Results"),
        rx.text(FormRadioState.form_data.to_string()),
        direction="column",
        spacing="2",
    )
```

## Radio Group Item

### value

The `value` given as data when submitted with a `name` on `rx.radio.root`.

### disabled

Use the `disabled` prop to create a disabled radiobutton. When `True`, prevents the user from interacting with the radio item. This differs from the `disabled` prop used by the `rx.radio.root`, which allows you to disable all the `rx.radio.item` components within the `rx.radio.root`.

```python demo
rx.flex(
    rx.radio.root(
        rx.flex(
            rx.text(
                rx.flex(
                    rx.radio.item(value="1"),
                    "Off",
                    spacing="2",
                ),
                as_="label",
                size="2",
            ),
            rx.text(
                rx.flex(
                    rx.radio.item(value="2"),
                    "On",
                    spacing="2",
                ),
                as_="label",
                size="2",
            ),
            direction="column",
            spacing="2",
        ),
    ),
    rx.radio.root(
        rx.flex(
            rx.text(
                rx.flex(
                    rx.radio.item(value="1", disabled=True),
                    "Off",
                    spacing="2",
                ),
                as_="label",
                size="2",
                color="gray",
            ),
            rx.text(
                rx.flex(
                    rx.radio.item(value="2"),
                    "On",
                    spacing="2",
                ),
                as_="label",
                size="2",
                color="gray",
            ),
            direction="column",
            spacing="2",
        ),
    ),
    direction="column",
    spacing="2",

)
```

### required

When `True`, indicates that the user must check the `radio_item_group` before the owning form can be submitted. This can only be used when a single `rx.radio.item` is used.

```python demo exec
class FormRadioState2(rx.State):
    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_example2():
    return rx.flex(
        rx.form.root(
            rx.flex(
                rx.radio.root(
                    rx.radio.item(value="1", required=True),
                    name="radio",
                ),
                rx.button("Submit", type="submit"),
                direction="column",
                spacing="2",
            ),
            on_submit=FormRadioState2.handle_submit,
            reset_on_submit=True,
        ),
        rx.divider(size="4"),
        rx.heading("Results"),
        rx.text(FormRadioState2.form_data.to_string()),
        direction="column",
        spacing="2",
    )
```

## Styling

### size

```python demo
rx.flex(
    rx.radio.root(
        rx.radio.item(value="1"),
        size="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        size="2",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        size="3",
    ),
    spacing="2",
)

```

### variant

```python demo
rx.flex(
    rx.flex(
        rx.radio.root(
            rx.radio.item(value="1"),
            rx.radio.item(value="2"),
            variant="surface",
            default_value="1",
        ),
        direction="column",
        spacing="2",
        as_child=True,
    ),
    rx.flex(
        rx.radio.root(
            rx.radio.item(value="1"),
            rx.radio.item(value="2"),
            variant="classic",
            default_value="1",
        ),
        direction="column",
        spacing="2",
        as_child=True,
    ),
    rx.flex(
        rx.radio.root(
            rx.radio.item(value="1"),
            rx.radio.item(value="2"),
            variant="soft",
            default_value="1",
        ),
        direction="column",
        spacing="2",
        as_child=True,
    ),
    spacing="2",
)
```

### color

```python demo
rx.flex(
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="indigo",
        default_value="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="cyan",
        default_value="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="orange",
        default_value="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="crimson",
        default_value="1",
    ),
    spacing="2"
)
```

### high_contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.grid(
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="cyan",
        default_value="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="cyan",
        default_value="1",
        high_contrast=True,
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="indigo",
        default_value="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="indigo",
        default_value="1",
        high_contrast=True,
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="orange",
        default_value="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="orange",
        default_value="1",
        high_contrast=True,
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="crimson",
        default_value="1",
    ),
    rx.radio.root(
        rx.radio.item(value="1"),
        color_scheme="crimson",
        default_value="1",
        high_contrast=True,
    ),
    rows="2",
    spacing="2",
    display="inline-grid",
    flow="column"
)
```

### alignment

Composing `rx.radio.item` within `text` automatically centers it with the first line of text.

```python demo
rx.flex(
    rx.radio.root(
        rx.text(
            rx.flex(
                rx.radio.item(value="1"),
                "Default",
                spacing="2",
            ),
            size="2",
            as_="label",
        ),
        rx.text(
            rx.flex(
                rx.radio.item(value="2"),
                "Compact",
                spacing="2",
            ),
            size="2",
            as_="label",
        ),
        default_value="1",
        size="1",
    ),
    rx.radio.root(
        rx.text(
            rx.flex(
                rx.radio.item(value="1"),
                "Default",
                spacing="2",
            ),
            size="3",
            as_="label",
        ),
        rx.text(
            rx.flex(
                rx.radio.item(value="2"),
                "Compact",
                spacing="2",
            ),
            size="3",
            as_="label",
        ),
        default_value="1",
        size="2",
    ),
    rx.radio.root(
        rx.text(
            rx.flex(
                rx.radio.item(value="1"),
                "Default",
                spacing="2",
            ),
            size="4",
            as_="label",
        ),
        rx.text(
            rx.flex(
                rx.radio.item(value="2"),
                "Compact",
                spacing="2",
            ),
            size="4",
            as_="label",
        ),
        default_value="1",
        size="3",
    ),
    spacing="3",
    direction="column",
)
```

```python eval
style_grid(component_used=rx.radio.root, component_used_str="radiogrouproot", variants=["classic", "surface", "soft"], components_passed=rx.radio.item(), disabled=True,)
```

## Real World Example

```python demo
rx.radio.root(
    rx.flex(
        rx.text(
            rx.flex(
                rx.radio.item(value="1"),
                "Default",
                spacing="2",
            ),
            size="2",
            as_="label",
        ),
        rx.text(
            rx.flex(
                rx.radio.item(value="2"),
                "Comfortable",
                gap="2",
            ),
            size="2",
            as_="label",
        ),
        rx.text(
            rx.flex(
                rx.radio.item(value="3"),
                "Compact",
                gap="2",
            ),
            size="2",
            as_="label",
        ),
        direction="column",
        gap="2",
    ),
    default_value="1",
)
```
