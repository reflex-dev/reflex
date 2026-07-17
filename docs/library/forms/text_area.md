---
components:
  - rx.text_area

TextArea: |
  lambda **props: rx.text_area(**props)
---

```python exec
import reflex as rx
```

# Text Area

A text area is a multi-line text input field.

## Basic Example

The text area component can be controlled by a single value. The `on_blur` prop can be used to update the value when the text area loses focus.

```python demo exec
class TextAreaBlur(rx.State):
    text: str = "Hello World!"

    @rx.event
    def set_text(self, text: str):
        self.text = text


def blur_example():
    return rx.vstack(
        rx.heading(TextAreaBlur.text, as_="h2"),
        rx.text_area(
            placeholder="Type here...",
            on_blur=TextAreaBlur.set_text,
        ),
    )
```

## Text Area in forms

Here we show how to use a text area in a form. We use the `name` prop to identify the text area in the form data. The form data is then passed to the `submit_feedback` method to be processed.

```python demo exec
class TextAreaFeedbackState(rx.State):
    feedback: str = ""
    submitted: bool = False

    @rx.event
    def set_feedback(self, value: str):
        self.feedback = value

    @rx.event
    def submit_feedback(self, form_data: dict):
        self.submitted = True

    @rx.event
    def reset_form(self):
        self.feedback = ""
        self.submitted = False


def feedback_form():
    return rx.cond(
        TextAreaFeedbackState.submitted,
        rx.card(
            rx.vstack(
                rx.text("Thank you for your feedback!"),
                rx.button(
                    "Submit another response", on_click=TextAreaFeedbackState.reset_form
                ),
            ),
        ),
        rx.card(
            rx.form(
                rx.flex(
                    rx.text("Are you enjoying Reflex?"),
                    rx.text_area(
                        placeholder="Write your feedback…",
                        value=TextAreaFeedbackState.feedback,
                        on_change=TextAreaFeedbackState.set_feedback,
                        resize="vertical",
                    ),
                    rx.button("Send", type="submit"),
                    direction="column",
                    spacing="3",
                ),
                on_submit=TextAreaFeedbackState.submit_feedback,
            ),
        ),
    )
```

## Submitting on Enter

By default, pressing Enter in a text area inserts a new line. Set the
`enter_key_submit` prop to submit the enclosing form when Enter is pressed
instead. Shift+Enter still inserts a new line, so multi-line input remains
possible.

```python demo exec
class EnterSubmitState(rx.State):
    submitted_text: str = ""

    @rx.event
    def handle_submit(self, form_data: dict):
        self.submitted_text = form_data["message"]


def enter_key_submit_example():
    return rx.vstack(
        rx.cond(
            EnterSubmitState.submitted_text != "",
            rx.text("Submitted: ", EnterSubmitState.submitted_text),
            rx.text("Nothing submitted yet."),
        ),
        rx.form(
            rx.text_area(
                name="message",
                placeholder="Type and press Enter to submit",
                enter_key_submit=True,
            ),
            on_submit=EnterSubmitState.handle_submit,
        ),
        width="100%",
    )
```

`enter_key_submit` accepts a Var, so it can be toggled dynamically — for
example, disabling Enter-to-submit while a previous submission is still being
processed: `enter_key_submit=~State.is_loading`.

```md alert warning
# `enter_key_submit` cannot be combined with `on_key_down`.

The `enter_key_submit` prop is implemented with its own key down handler, so
passing both to the same component raises an error. Note that a Python
`on_key_down` handler receives only the key and modifier flags, not the raw
event, so it cannot call `preventDefault()` to stop Enter from inserting a
newline. Replicating Enter-to-submit alongside custom key handling therefore
needs a client-side handler (e.g. via `rx.call_script`), not a plain
`on_key_down` event handler.
```
