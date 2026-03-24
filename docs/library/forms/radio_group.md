---
components:
  - rx.radio_group
  - rx.radio_group.root
  - rx.radio_group.item

HighLevelRadioGroup: |
  lambda **props: rx.radio_group(["1", "2", "3", "4", "5"], **props)

RadioGroupRoot: |
  lambda **props: rx.radio_group.root(
      rx.radio_group.item(value="1"),
      rx.radio_group.item(value="2"),
      rx.radio_group.item(value="3"),
      rx.radio_group.item(value="4"),
      rx.radio_group.item(value="5"),
      **props
  )

RadioGroupItem: |
  lambda **props: rx.radio_group.root(
      rx.radio_group.item(value="1", **props),
      rx.radio_group.item(value="2", **props),
      rx.radio_group.item(value="3",),
      rx.radio_group.item(value="4",),
      rx.radio_group.item(value="5",),
  )
---

```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
```

# Radio Group

A set of interactive radio buttons where only one can be selected at a time.

## Basic example

```python demo exec
class RadioGroupState(rx.State):
    item: str = "No Selection"

    @rx.event
    def set_item(self, item: str):
        self.item = item

def radio_group_state_example():
    return rx.vstack(
        rx.badge(RadioGroupState.item, color_scheme="green"),
        rx.radio(["1", "2", "3"], on_change=RadioGroupState.set_item, direction="row"),
    )
```

## Submitting a form using Radio Group

The `name` prop is used to name the group. It is submitted with its owning form as part of a name/value pair.

When the `required` prop is `True`, it indicates that the user must check a radio item before the owning form can be submitted.

```python demo exec
class FormRadioState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def radio_form_example():
    return rx.card(
        rx.vstack(
            rx.heading("Example Form"),
            rx.form.root(
                rx.vstack(
                    rx.radio_group(
                        ["Option 1", "Option 2", "Option 3"],
                        name="radio_choice",
                        direction="row",
                    ),
                    rx.button("Submit", type="submit"),
                    width="100%",
                    spacing="4",
                ),
                on_submit=FormRadioState.handle_submit,
                reset_on_submit=True,
            ),
            rx.divider(),
            rx.hstack(
                rx.heading("Results:"),
                rx.badge(FormRadioState.form_data.to_string()),
            ),
            align_items="left",
            width="100%",
            spacing="4",
        ),
        width="50%",
    )
```
