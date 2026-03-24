---
components:
  - rx.switch

Switch: |
  lambda **props: rx.switch(**props)
---

```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
from pcweb.pages.docs import vars
```

# Switch

A toggle switch alternative to the checkbox.

## Basic Example

Here is a basic example of a switch. We use the `on_change` trigger to toggle the value in the state.

```python demo exec
class SwitchState(rx.State):
    value: bool = False

    @rx.event
    def set_end(self, value: bool):
        self.value = value

def switch_intro():
    return rx.center(
        rx.switch(on_change=SwitchState.set_end),
        rx.badge(SwitchState.value),
    )
```

## Control the value

The `checked` prop is used to control the state of the switch. The event `on_change` is called when the state of the switch changes, when the `change_checked` event handler is called.

The `disabled` prop when `True`, prevents the user from interacting with the switch. In our example below, even though the second switch is `disabled` we are still able to change whether it is checked or not using the `checked` prop.

```python demo exec
class ControlSwitchState(rx.State):

    checked = True

    @rx.event
    def change_checked(self, checked: bool):
        """Change the switch checked var."""
        self.checked = checked


def control_switch_example():
    return rx.hstack(
        rx.switch(
            checked=ControlSwitchState.checked,
            on_change=ControlSwitchState.change_checked,
        ),
        rx.switch(
            checked=ControlSwitchState.checked,
            on_change=ControlSwitchState.change_checked,
            disabled=True,
        ),
    )
```

## Switch in forms

The `name` of the switch is needed to submit with its owning form as part of a name/value pair. When the `required` prop is `True`, it indicates that the user must check the switch before the owning form can be submitted.

The `value` prop is only used for form submission, use the `checked` prop to control state of the `switch`.

```python demo exec
class FormSwitchState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def switch_form_example():
    return rx.card(
            rx.vstack(
                rx.heading("Example Form"),
                rx.form.root(
                    rx.hstack(
                        rx.switch(name="switch"),
                        rx.button("Submit", type="submit"),
                        width="100%",
                    ),
                    on_submit=FormSwitchState.handle_submit,
                    reset_on_submit=True,
                ),
                rx.divider(),
                rx.hstack(
                    rx.heading("Results:"),
                    rx.badge(FormSwitchState.form_data.to_string()),
                ),
                align_items="left",
                width="100%",
            ),
        width="50%",
    )
```
