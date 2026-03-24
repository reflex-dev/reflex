---
components:
    - rx.code
---

```python exec
import reflex as rx
```

# Code

```python demo
rx.code("console.log()")
```

## Size

Use the `size` prop to control text size. This prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.code("console.log()", size="1"),
    rx.code("console.log()", size="2"),
    rx.code("console.log()", size="3"),
    rx.code("console.log()", size="4"),
    rx.code("console.log()", size="5"),
    rx.code("console.log()", size="6"),
    rx.code("console.log()", size="7"),
    rx.code("console.log()", size="8"),
    rx.code("console.log()", size="9"),
    direction="column",
    spacing="3",
    align="start",
)
```

## Weight

Use the `weight` prop to set the text weight.

```python demo
rx.flex(
    rx.code("console.log()", weight="light"),
    rx.code("console.log()", weight="regular"),
    rx.code("console.log()", weight="medium"),
    rx.code("console.log()", weight="bold"),
    direction="column",
    spacing="3",
)
```

## Variant

Use the `variant` prop to control the visual style.

```python demo
rx.flex(
    rx.code("console.log()", variant="solid"),
    rx.code("console.log()", variant="soft"),
    rx.code("console.log()", variant="outline"),
    rx.code("console.log()", variant="ghost"),
    direction="column",
    spacing="2",
    align="start",
)
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.code("console.log()", color_scheme="indigo"),
    rx.code("console.log()", color_scheme="crimson"),
    rx.code("console.log()", color_scheme="orange"),
    rx.code("console.log()", color_scheme="cyan"),
    direction="column",
    spacing="2",
    align="start",
)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.flex(
        rx.code("console.log()", variant="solid"),
        rx.code("console.log()", variant="soft"),
        rx.code("console.log()", variant="outline"),
        rx.code("console.log()", variant="ghost"),
        direction="column",
        align="start",
        spacing="2",
    ),
    rx.flex(
        rx.code("console.log()", variant="solid", high_contrast=True),
        rx.code("console.log()", variant="soft", high_contrast=True),
        rx.code("console.log()", variant="outline", high_contrast=True),
        rx.code("console.log()", variant="ghost", high_contrast=True),
        direction="column",
        align="start",
        spacing="2",
    ),
    spacing="3",
)
```
