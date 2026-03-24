---
components:
    - rx.input
    - rx.input.slot
---

```python exec
import reflex as rx
```

# Input

A text field is an input field that users can type into. This component uses Radix's [text field](https://www.radix-ui.com/themes/docs/components/text-field) component.


## Overview

The TextField component is used to capture user input and can include an optional slot for buttons and icons. It is based on the <div> element and supports common margin props.

## Basic Example

```python demo
rx.input(
    rx.input.slot(
        rx.icon(tag="search"),

    ),
    placeholder="Search here...",
)
```

## Stateful Example with Blur Event

```python demo exec
class TextfieldBlur1(rx.State):
    text: str = "Hello World!"

    @rx.event
    def set_text(self, text: str):
        self.text = text

def blur_example1():
    return rx.vstack(
        rx.heading(TextfieldBlur1.text),
        rx.input(
            rx.input.slot(
                rx.icon(tag="search"),
            ),
            placeholder="Search here...",
            on_blur=TextfieldBlur1.set_text,
        )
    )
```

## Controlled Example

```python demo exec
class TextfieldControlled1(rx.State):
    text: str = "Hello World!"

    @rx.event
    def set_text(self, text: str):
        self.text = text

def controlled_example1():
    return rx.vstack(
        rx.heading(TextfieldControlled1.text),
        rx.input(
            rx.input.slot(
                rx.icon(tag="search"),
            ),
            placeholder="Search here...",
            value=TextfieldControlled1.text,
            on_change=TextfieldControlled1.set_text,
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
        rx.input(
            rx.input.slot(
                rx.icon(tag="search"),
            ),
            placeholder="Search songs...",
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
