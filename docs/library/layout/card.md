---
components:
  - rx.radix.card

Card: |
    lambda **props: rx.radix.themes.card("Basic Card ", **props)
---

```python exec
import reflex as rx
```

# Card

A Card component is used for grouping related components. It is similar to the Box, except it has a
border, uses the theme colors and border radius, and provides a `size` prop to control spacing
and margin according to the Radix `"1"` - `"5"` scale.

The Card requires less styling than a Box to achieve consistent visual results when used with
themes.

## Basic Example

```python demo
rx.flex(
    rx.card("Card 1", size="1"),
    rx.card("Card 2", size="2"),
    rx.card("Card 3", size="3"),
    rx.card("Card 4", size="4"),
    rx.card("Card 5", size="5"),
    spacing="2",
    align_items="flex-start",
    flex_wrap="wrap",
)
```

## Rendering as a Different Element

The `as_child` prop may be used to render the Card as a different element. Link and Button are
commonly used to make a Card clickable.

```python demo
rx.card(
    rx.link(
        rx.flex(
            rx.avatar(src="/reflex_banner.png"),
            rx.box(
                rx.heading("Quick Start"),
                rx.text("Get started with Reflex in 5 minutes."),
            ),
            spacing="2",
        ),
    ),
    as_child=True,
)
```

## Using Inset Content
