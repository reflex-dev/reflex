---
components:
  - rx.form
  - rx.form.root
  - rx.form.field
  - rx.form.control
  - rx.form.label
  - rx.form.message
  - rx.form.submit

FormRoot: |
  lambda **props: rx.form.root(
      rx.form.field(
          rx.flex(
              rx.form.label("Email"),
              rx.form.control(
                  rx.input(
                      placeholder="Email Address",
                      # type attribute is required for "typeMismatch" validation
                      type="email",
                  ),
                  as_child=True,
              ),
              rx.form.message("Please enter a valid email"),
              rx.form.submit(
                  rx.button("Submit"),
                  as_child=True,
              ),
              direction="column",
              spacing="2",
              align="stretch",
          ),
          name="email",
      ),
      **props,
  )

FormField: |
  lambda **props: rx.form.root(
      rx.form.field(
          rx.flex(
              rx.form.label("Email"),
              rx.form.control(
                  rx.input(
                      placeholder="Email Address",
                      # type attribute is required for "typeMismatch" validation
                      type="email",
                  ),
                  as_child=True,
              ),
              rx.form.message("Please enter a valid email", match="typeMismatch"),
              rx.form.submit(
                  rx.button("Submit"),
                  as_child=True,
              ),
              direction="column",
              spacing="2",
              align="stretch",
          ),
          **props,
      ),
      reset_on_submit=True,
  )

FormLabel: |
  lambda **props: rx.form.root(
      rx.form.field(
          rx.flex(
              rx.form.label("Email", **props,),
              rx.form.control(
                  rx.input(
                      placeholder="Email Address",
                      # type attribute is required for "typeMismatch" validation
                      type="email",
                  ),
                  as_child=True,
              ),
              rx.form.message("Please enter a valid email", match="typeMismatch"),
              rx.form.submit(
                  rx.button("Submit"),
                  as_child=True,
              ),
              direction="column",
              spacing="2",
              align="stretch",
          ),
      ),
      reset_on_submit=True,
  )

FormMessage: |
  lambda **props: rx.form.root(
              rx.form.field(
                  rx.flex(
                      rx.form.label("Email"),
                      rx.form.control(
                          rx.input(
                              placeholder="Email Address",
                              # type attribute is required for "typeMismatch" validation
                              type="email",
                          ),
                          as_child=True,
                      ),
                      rx.form.message("Please enter a valid email", **props,),
                      rx.form.submit(
                          rx.button("Submit"),
                          as_child=True,
                      ),
                      direction="column",
                      spacing="2",
                      align="stretch",
                  ),
                  name="email",
              ),
              on_submit=lambda form_data: rx.window_alert(form_data.to_string()),
              reset_on_submit=True,
          )
---

```python exec
import reflex as rx
```

# Form

Forms are used to collect user input. The `rx.form` component is used to group inputs and submit them together.

The form component's children can be form controls such as `rx.input`, `rx.checkbox`, `rx.slider`, `rx.textarea`, `rx.radio_group`, `rx.select` or `rx.switch`. The controls should have a `name` attribute that is used to identify the control in the form data. The `on_submit` event trigger submits the form data as a dictionary to the `handle_submit` event handler.

The form is submitted when the user clicks the submit button or presses enter on the form controls.

```python demo exec
class FormState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_example():
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.input(placeholder="First Name", name="first_name"),
                rx.input(placeholder="Last Name", name="last_name"),
                rx.hstack(
                    rx.checkbox("Checked", name="check"),
                    rx.switch("Switched", name="switch"),
                ),
                rx.button("Submit", type="submit"),
            ),
            on_submit=FormState.handle_submit,
            reset_on_submit=True,
        ),
        rx.divider(),
        rx.heading("Results"),
        rx.text(FormState.form_data.to_string()),
    )
```

```md alert warning
# When using the form you must include a button or input with `type='submit'`.
```

```md alert info
# Using `name` vs `id`.

When using the `name` attribute in form controls like `rx.switch`, `rx.radio_group`, and `rx.checkbox`, these controls will only be included in the form data if their values are set (e.g., if the checkbox is checked, the switch is toggled, or a radio option is selected).

If you need these controls to be passed in the form data even when their values are not set, you can use the `id` attribute instead of name. The id attribute ensures that the control is always included in the submitted form data, regardless of whether its value is set or not.
```

```md video https://youtube.com/embed/ITOZkzjtjUA?start=5287&end=6040
# Video: Forms
```

## Dynamic Forms

Forms can be dynamically created by iterating through state vars using `rx.foreach`.

This example allows the user to add new fields to the form prior to submit, and all
fields will be included in the form data passed to the `handle_submit` function.

```python demo exec
class DynamicFormState(rx.State):
    form_data: dict = {}
    form_fields: list[str] = ["first_name", "last_name", "email"]

    @rx.var(cache=True)
    def form_field_placeholders(self) -> list[str]:
        return [
            " ".join(w.capitalize() for w in field.split("_"))
            for field in self.form_fields
        ]

    @rx.event
    def add_field(self, form_data: dict):
        new_field = form_data.get("new_field")
        if not new_field:
            return
        field_name = new_field.strip().lower().replace(" ", "_")
        self.form_fields.append(field_name)

    @rx.event
    def handle_submit(self, form_data: dict):
        self.form_data = form_data


def dynamic_form():
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.foreach(
                    DynamicFormState.form_fields,
                    lambda field, idx: rx.input(
                        placeholder=DynamicFormState.form_field_placeholders[idx],
                        name=field,
                    ),
                ),
                rx.button("Submit", type="submit"),
            ),
            on_submit=DynamicFormState.handle_submit,
            reset_on_submit=True,
        ),
        rx.form(
            rx.hstack(
                rx.input(placeholder="New Field", name="new_field"),
                rx.button("+", type="submit"),
            ),
            on_submit=DynamicFormState.add_field,
            reset_on_submit=True,
        ),
        rx.divider(),
        rx.heading("Results"),
        rx.text(DynamicFormState.form_data.to_string()),
    )
```
