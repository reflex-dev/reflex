---
components:
  - rx.radix.box
---

```python exec
import reflex as rx
```

# Box

Box is a generic container component that can be used to group other components.

By default, the Box component is based on the `div` and rendered as a block element. It's primary use is for applying styles.

## Basic Example

```python demo
rx.box(
    rx.box("CSS color", background_color="yellow", border_radius="2px", width="20%", margin="4px", padding="4px"),
    rx.box("CSS color", background_color="orange", border_radius="5px", width="40%", margin="8px", padding="8px"),
    rx.box("Radix Color", background_color="var(--tomato-3)", border_radius="5px", width="60%", margin="12px", padding="12px"),
    rx.box("Radix Color", background_color="var(--plum-3)", border_radius="10px", width="80%", margin="16px", padding="16px"),
    rx.box("Radix Theme Color", background_color="var(--accent-2)", radius="full", width="100%", margin="24px", padding="25px"),
    flex_grow="1",
    text_align="center",
)
```

## Background

To set a background [image](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_images) or
[gradient](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_images/Using_CSS_gradients),
use the [`background` CSS prop](https://developer.mozilla.org/en-US/docs/Web/CSS/background).

```python demo
rx.flex(
    rx.box(background="linear-gradient(45deg, var(--tomato-9), var(--plum-9))", width="20%", height="100%"),
    rx.box(background="linear-gradient(red, yellow, blue, orange)", width="20%", height="100%"),
    rx.box(background="radial-gradient(at 0% 30%, red 10px, yellow 30%, #1e90ff 50%)", width="20%", height="100%"),
    rx.box(background="center/cover url('/reflex_banner.png')", width="20%", height="100%"),
    spacing="2",
    width="100%",
    height="10vh",
)
```
