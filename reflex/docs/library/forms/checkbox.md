---
components:
  - rx.checkbox

HighLevelCheckbox: |
  lambda **props: rx.checkbox("Basic Checkbox", **props)
---

```python exec
import reflex as rx
```

# Checkbox

## Basic Example

The `on_change` trigger is called when the `checkbox` is clicked.

```python demo exec
class CheckboxState(rx.State):
    checked: bool = False

    @rx.event
    def set_checked(self, value: bool):
        self.checked = value

def checkbox_example():
    return rx.vstack(
        rx.heading(CheckboxState.checked),
        rx.checkbox(on_change=CheckboxState.set_checked),
    )
```

The `input` prop is used to set the `checkbox` as a controlled component.

```python demo exec
class FormCheckboxState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        print(form_data)
        self.form_data = form_data


def form_checkbox_example():
    return rx.card(
        rx.vstack(
            rx.heading("Example Form"),
            rx.form.root(
                rx.hstack(
                    rx.checkbox(
                        name="checkbox",
                        label="Accept terms and conditions",
                    ),
                    rx.button("Submit", type="submit"),
                    width="100%",
                ),
                on_submit=FormCheckboxState.handle_submit,
                reset_on_submit=True,
            ),
            rx.divider(),
            rx.hstack(
                rx.heading("Results:"),
                rx.badge(FormCheckboxState.form_data.to_string()),
            ),
            align_items="left",
            width="100%",
        ),
        width="50%",
    )
```
