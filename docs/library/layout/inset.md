---
components:
    - rx.radix.inset

Inset: |
    lambda **props: rx.radix.themes.card(
        rx.radix.themes.inset(
            rx.image(src="/reflex_banner.png", height="auto"),
            **props,
        ),
        width="500px",
    )
    
---

```python exec
import reflex as rx
```

# Inset

Applies a negative margin to allow content to bleed into the surrounding container.

## Basic Example

Nesting an Inset component inside a Card will render the content from edge to edge of the card.

```python demo
rx.card(
    rx.inset(
        rx.image(src="/reflex_banner.png", width="100%", height="auto"),
        side="top",
        pb="current",
    ),
    rx.text("Reflex is a web framework that allows developers to build their app in pure Python."),
    width="25vw",
)
```

## Other Directions

The `side` prop controls which side the negative margin is applied to. When using a specific side,
it is helpful to set the padding for the opposite side to `current` to retain the same padding the
content would have had if it went to the edge of the parent component.

```python demo
rx.card(
    rx.text("The inset below uses a bottom side."),
    rx.inset(
        rx.image(src="/reflex_banner.png", width="100%", height="auto"),
        side="bottom",
        pt="current",
    ),
    width="25vw",
)
```

```python demo
rx.card(
    rx.flex(
        rx.text("This inset uses a right side, which requires a flex with direction row."),
        rx.inset(
            rx.box(background="center/cover url('/reflex_banner.png')", height="100%"),
            width="100%",
            side="right",
            pl="current",
        ),
        direction="row",
        width="100%",
    ),
    width="25vw",
)
```

```python demo
rx.card(
    rx.flex(
        rx.inset(
            rx.box(background="center/cover url('/reflex_banner.png')", height="100%"),
            width="100%",
            side="left",
            pr="current",
        ),
        rx.text("This inset uses a left side, which also requires a flex with direction row."),
        direction="row",
        width="100%",
    ),
    width="25vw",
)
```
