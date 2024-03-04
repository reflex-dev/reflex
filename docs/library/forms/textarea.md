---
components:
    - rx.radix.text_area

TextArea: |
    lambda **props: rx.radix.themes.text_area(**props)
---

```python exec
import reflex as rx
```

# TextArea

A text area is a multi-line text input field. This component uses Radix's [text area](https://radix-ui.com/primitives/docs/components/text-area) component.

## Basic Example

```python demo
rx.text_area(
    placeholder="Type here...",
)
```

```python demo exec
class TextAreaBlur(rx.State):
    text: str = "Hello World!"


def blur_example():
    return rx.vstack(
        rx.heading(TextAreaBlur.text),
        rx.text_area(
            on_blur=TextAreaBlur.set_text,
        ),
    )
```

```python demo exec
class TextAreaControlled(rx.State):
    text: str = "Hello World!"


def controlled_example():
    return rx.vstack(
        rx.heading(TextAreaControlled.text),
        rx.text_area(
            value=TextAreaControlled.text,
            on_change=TextAreaControlled.set_text,
        ),
        rx.text_area(
            value="Simon says: " + TextAreaControlled.text,
        ),
    )
```

# Real World Example

```python demo
rx.card(
    rx.flex(
        rx.text("Are you enjoying Reflex?"),
        rx.text_area(placeholder="Write your feedback…"),
        rx.flex(
            rx.text("Attach screenshot?", size="2"),
            rx.switch(size="1", default_checked=True),
            justify="between",
        ),
        rx.grid(
            rx.button("Back", variant="surface"),
            rx.button("Send"),
            columns="2",
            spacing="2",
        ),
        direction="column",
        spacing="3",
    ),
    style={"maxWidth": 500},
)
```
