---
components:
    - rx.radix.text_field
    - rx.radix.text_field.root
    - rx.radix.text_field.input
    - rx.radix.text_field.slot
---

```python exec
import reflex as rx
```

# TextField

A text field is an input field that users can type into. This component uses Radix's [text field](https://radix-ui.com/primitives/docs/components/text-field) component.

## Basic Example

```python demo
rx.radix.text_field.root(
    rx.radix.text_field.slot(
        rx.icon(tag="search"),
    ),
    rx.radix.text_field.input(
        placeholder="Search here...",
    ),
)
```

```python demo exec
class TextfieldBlur1(rx.State):
    text: str = "Hello World!"


def blur_example1():
    return rx.vstack(
        rx.heading(TextfieldBlur1.text),
        rx.radix.text_field.root(
            rx.radix.text_field.slot(
                rx.icon(tag="search"),
            ),
            rx.radix.text_field.input(
                placeholder="Search here...",
                on_blur=TextfieldBlur1.set_text,
            ),
            
        )
    )
```

```python demo exec
class TextfieldControlled1(rx.State):
    text: str = "Hello World!"


def controlled_example1():
    return rx.vstack(
        rx.heading(TextfieldControlled1.text),
        rx.radix.text_field.root(
            rx.radix.text_field.slot(
                rx.icon(tag="search"),
            ),
            rx.radix.text_field.input(
                placeholder="Search here...",
                value=TextfieldControlled1.text,
                on_change=TextfieldControlled1.set_text,
            ),
        ),
    )
```

# Real World Example

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
        rx.radix.text_field.root(
            rx.radix.text_field.slot(
                rx.icon(tag="search"),
            ),
            rx.radix.text_field.input(
                placeholder="Search songs...",
            ),
        ),
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
