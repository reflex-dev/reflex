---
components:
    - rx.radix.input
    - rx.radix.text_field.root
    - rx.radix.text_field.input
    - rx.radix.text_field.slot


Input: |
    lambda **props: rx.input(placeholder="Search the docs", **props)

TextFieldRoot: |
    lambda **props: rx.radix.themes.text_field.root(
        rx.radix.themes.text_field.slot(
            rx.icon(tag="search", height="16", width="16"),
        ),
        rx.radix.themes.text_field.input(placeholder="Search the docs"),
        **props,
    )

TextFieldInput: |
    lambda **props: rx.radix.themes.text_field.root(
        rx.radix.themes.text_field.slot(
            rx.icon(tag="search", height="16", width="16"),
        ),
        rx.radix.themes.text_field.input(placeholder="Search the docs", **props,),
    )

TextFieldSlot: |
    lambda **props: rx.radix.themes.text_field.root(
        rx.radix.themes.text_field.slot(
            rx.icon(tag="search", height="16", width="16"),
            **props,
        ),
        rx.radix.themes.text_field.input(placeholder="Search the docs"),
    )
---

```python exec
import reflex as rx
from pcweb.pages.docs import library
```

# Input (High Level API for TextField)

The `input` component is an input field that users can type into.

## Basic Example

```python demo
rx.input()
```

### Setting Defaults

Can set defaults for a `placeholder` for text to show in the `input` box before any text is input into it.

Can limit the `max_length` allowed as input into the `input` box.

```python demo
rx.input(placeholder="Search here...", max_length="20")
```

### Using Event Handlers

The `on_blur` event handler is called when focus has left the `input` for example, it’s called when the user clicks outside of a focused text input.

```python demo exec
class TextfieldBlur(rx.State):
    text: str = "Hello World!"


def blur_example():
    return rx.vstack(
        rx.heading(TextfieldBlur.text),
        rx.input(
            placeholder="Search here...", 
            on_blur=TextfieldBlur.set_text,
        ),
    )
```

The `on_change` event handler is called when the `value` of `input` has changed.

```python demo exec
class TextfieldControlled(rx.State):
    text: str = "Hello World!"


def controlled_example():
    return rx.vstack(
        rx.heading(TextfieldControlled.text),
        rx.input(
            placeholder="Search here...", 
            value=TextfieldControlled.text,
            on_change=TextfieldControlled.set_text,
        ),
    )
```

Behind the scene, the input component is implemented using debounced input to avoid sending individual state updates per character to the backend while the user is still typing. This allows a state var to directly control the `value` prop from the backend without the user experiencing input lag. For advanced use cases, you can tune the debounce delay by setting the `debounce_timeout` when creating the Input component. You can find examples of how it is used in the [DebouncedInput]({library.forms.debounce.path}) component.

### Submitting a form using input

The `name` prop is needed to submit with its owning form as part of a name/value pair.

When the `required` prop is `True`, it indicates that the user must input text before the owning form can be submitted.

The `type` is set here to `password`. The element is presented as a one-line plain text editor control in which the text is obscured so that it cannot be read. The `type` prop can take any value of `email`, `file`, `password`, `text` and several others. Learn more [here](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input).

```python demo exec
class FormInputState(rx.State):
    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_input1():
    return rx.vstack(
        rx.form.root(
            rx.vstack(
                rx.input(name="input", default_value="search", placeholder="Input text here...", type="password", required=True),
                rx.button("Submit", type="submit"),
                width="100%",
            ),
            on_submit=FormInputState.handle_submit,
            reset_on_submit=True,
            width="100%",
        ),
        rx.divider(width="100%"),
        rx.heading("Results"),
        rx.text(FormInputState.form_data.to_string()),
        width="100%",
    )
```

To learn more about how to use forms in the [Form]({library.forms.form.path}) docs.

## Real World Example

```python demo exec

def song(title, initials: str, genre: str):
    return rx.card(rx.flex(
        rx.flex(
            rx.avatar(fallback=initials),
            rx.flex(
                rx.text(title, size="2", weight="bold"),
                rx.text(genre, size="1", color_scheme="gray"),
                direction="column",
                spacing="1",
            ),
            direction="row",
            align_items="left",
            spacing="1",
        ),
        rx.flex(
            rx.icon(tag="chevron_right"),
            align_items="center",
        ),
        justify="between",
    ))


def search():
    return rx.card(
    rx.flex(
        rx.input(placeholder="Search songs...", ),
        rx.flex(
            song("The Less I Know", "T", "Rock"),
            song("Breathe Deeper", "ZB", "Rock"),
            song("Let It Happen", "TF", "Rock"),
            song("Borderline", "ZB", "Pop"),
            song("Lost In Yesterday", "TO", "Rock"),
            song("Is It True", "TO", "Rock"),
            direction="column",
            spacing="1",
        ),
        direction="column",
        spacing="3",
    ),
    style={"maxWidth": 500},
)
```
