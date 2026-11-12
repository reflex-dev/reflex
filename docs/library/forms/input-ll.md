---
components:
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

```python test
def test_input_with_slot(demo):
    expect(demo.get_by_role("textbox")).to_have_attribute(
        "placeholder", "Search here..."
    )
    expect(demo.locator("svg.lucide-search")).to_have_count(1)
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
        rx.heading(TextfieldBlur1.text, as_="h2"),
        rx.input(
            rx.input.slot(
                rx.icon(tag="search"),
            ),
            placeholder="Search here...",
            on_blur=TextfieldBlur1.set_text,
        ),
    )
```

```python test
def test_input_updates_on_blur(demo):
    heading = demo.get_by_role("heading")
    expect(heading).to_have_text("Hello World!")
    textbox = demo.get_by_placeholder("Search here...")
    textbox.fill("Reflex")
    expect(heading).to_have_text("Hello World!")
    textbox.blur()
    expect(heading).to_have_text("Reflex")
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
        rx.heading(TextfieldControlled1.text, as_="h2"),
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

```python test
def test_controlled_input(demo):
    textbox = demo.get_by_placeholder("Search here...")
    expect(textbox).to_have_value("Hello World!")
    textbox.fill("Controlled")
    expect(demo.get_by_role("heading")).to_have_text("Controlled")
```

## Real World Example

```python demo exec
def song(title, initials: str, genre: str):
    return rx.card(
        rx.flex(
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
        )
    )


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

```python test
def test_song_search_card(demo):
    expect(demo.get_by_placeholder("Search songs...")).to_be_visible()
    for title in [
        "The Less I Know",
        "Breathe Deeper",
        "Let It Happen",
        "Borderline",
        "Lost In Yesterday",
        "Is It True",
    ]:
        expect(demo.get_by_text(title, exact=True)).to_be_visible()
    expect(demo.get_by_text("Rock", exact=True)).to_have_count(5)
    expect(demo.get_by_text("Pop", exact=True)).to_have_count(1)
```
