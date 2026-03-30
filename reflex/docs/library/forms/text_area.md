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
        rx.heading(TextAreaBlur.text),
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
                rx.button("Submit another response", on_click=TextAreaFeedbackState.reset_form),
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
