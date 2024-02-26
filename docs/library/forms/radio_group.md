---
components:
    - rx.radix.radio_group
    - rx.radix.radio_group.root
    - rx.radix.radio_group.item

HighLevelRadioGroup: |
    lambda **props: rx.radix.themes.radio_group(["1", "2", "3", "4", "5"], **props)

RadioGroupRoot: |
    lambda **props: rx.radix.themes.radio_group.root(
        rx.radix.themes.radio_group.item(value="1"),
        rx.radix.themes.radio_group.item(value="2"),
        rx.radix.themes.radio_group.item(value="3"),
        rx.radix.themes.radio_group.item(value="4"),
        rx.radix.themes.radio_group.item(value="5"),
        **props
    )

RadioGroupItem: |
    lambda **props: rx.radix.themes.radio_group.root(
        rx.radix.themes.radio_group.item(value="1", **props),
        rx.radix.themes.radio_group.item(value="2", **props),
        rx.radix.themes.radio_group.item(value="3",),
        rx.radix.themes.radio_group.item(value="4",),
        rx.radix.themes.radio_group.item(value="5",),
    )
---


```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
```

# High Level Radio Group

A set of interactive radio buttons where only one can be selected at a time.

## Basic example

```python demo
rx.radio(["1", "2", "3"], default_value="1")
```

The `default_value` prop can be used to set the value of the radio item that should be checked when initially rendered.

## Setting direction, spacing and size

The direction of the `radio_group` can be set using the `direction` prop which takes values `'row' | 'column' | 'row-reverse' | 'column-reverse' |`.

The gap between the `radio_group` items can also be set using the `gap` prop, which takes values `'1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' |`.

The size of the `radio_group` items and the associated text can be set with the `size` prop, which can take values `1' | '2' | '3' |`

```python demo
rx.radio(["1", "2", "3", "4", "5"], direction="row", spacing="8", size="3")
```

## Using State Vars in the RadioGroup

State vars can also be passed in as the `items` to the `radiogroup`.

```python demo exec
class RadioState_HL1(rx.State):
    items: list[str] = ["1", "2", "3"]

def radio_state_example_HL1():
    return rx.radio(RadioState_HL1.items, direction="row", spacing="9")
```

### Control the value

The controlled `value` of the radio item to check. Should be used in conjunction with `on_change` event handler.

```python demo exec
class RadioState_HL(rx.State):
    text: str = "No Selection"


def radio_state_example_HL():
    return rx.vstack(
        rx.badge(RadioState_HL.text, color_scheme="green"),
        rx.radio(["1", "2", "3"], on_change=RadioState_HL.set_text),
    )
```

When the `disabled` prop is set to `True`, it prevents the user from interacting with radio items.

```python demo
rx.flex(
    rx.radio(["1", "2"]),
    rx.radio(["1", "2"], disabled=True),
    spacing="2",
)

```

### Submitting a form using Radio Group

The `name` prop is used to name the group. It is submitted with its owning form as part of a name/value pair.

When the `required` prop is `True`, it indicates that the user must check a radio item before the owning form can be submitted.

```python demo exec
class FormRadioState_HL(rx.State):
    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_example_HL():
    return rx.vstack(
        rx.form.root(
            rx.vstack(
                rx.radio(["1", "2", "3"], name="radio", required=True,),
                rx.button("Submit", type="submit"),
            ),
            on_submit=FormRadioState_HL.handle_submit,
            reset_on_submit=True,
        ),
        rx.divider(width="100%"),
        rx.heading("Results"),
        rx.text(FormRadioState_HL.form_data.to_string()),
    )
```
