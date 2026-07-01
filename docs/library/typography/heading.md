---
components:
  - rx.heading
---

```python exec
import reflex as rx
```

# Heading

```python demo
rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2")
```

## As another element

Use the `as_` prop to change the heading level. This prop is purely semantic and does not change the visual appearance.

```python demo
rx.flex(
    rx.heading("Level 1", as_="h2"),
    rx.heading("Level 2", as_="h2"),
    rx.heading("Level 3", as_="h3"),
    direction="column",
    spacing="3",
)
```

## Size

Use the `size` prop to control the size of the heading. The prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease

```python demo
rx.flex(
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="1"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="2"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="3"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="4"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="5"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="6"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="7"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="8"),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", size="9"),
    direction="column",
    spacing="3",
)
```

## Weight

Use the `weight` prop to set the text weight.

```python demo
rx.flex(
    rx.heading(
        "The quick brown fox jumps over the lazy dog.", as_="h2", weight="light"
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.", as_="h2", weight="regular"
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.", as_="h2", weight="medium"
    ),
    rx.heading("The quick brown fox jumps over the lazy dog.", as_="h2", weight="bold"),
    direction="column",
    spacing="3",
)
```

## Align

Use the `align` prop to set text alignment.

```python demo
rx.flex(
    rx.heading("Left-aligned", as_="h2", align="left"),
    rx.heading("Center-aligned", as_="h2", align="center"),
    rx.heading("Right-aligned", as_="h2", align="right"),
    direction="column",
    spacing="3",
    width="100%",
)
```

## Trim

Use the `trim` prop to trim the leading space at the start, end, or both sides of the text.

```python demo
rx.flex(
    rx.heading(
        "Without Trim",
        as_="h2",
        trim="normal",
        style={
            "background": "var(--gray-a2)",
            "border_top": "1px dashed var(--gray-a7)",
            "border_bottom": "1px dashed var(--gray-a7)",
        },
    ),
    rx.heading(
        "With Trim",
        as_="h2",
        trim="both",
        style={
            "background": "var(--gray-a2)",
            "border_top": "1px dashed var(--gray-a7)",
            "border_bottom": "1px dashed var(--gray-a7)",
        },
    ),
    direction="column",
    spacing="3",
)
```

Trimming the leading is useful when dialing in vertical spacing in cards or other “boxy” components. Otherwise, padding looks larger on top and bottom than on the sides.

```python demo
rx.flex(
    rx.box(
        rx.heading(
            "Without trim",
            as_="h2",
            margin_bottom="4px",
            size="3",
        ),
        rx.text(
            "The goal of typography is to relate font size, line height, and line width in a proportional way that maximizes beauty and makes reading easier and more pleasant."
        ),
        style={
            "background": "var(--gray-a2)",
            "border": "1px dashed var(--gray-a7)",
        },
        padding="16px",
    ),
    rx.box(
        rx.heading("With trim", as_="h2", margin_bottom="4px", size="3", trim="start"),
        rx.text(
            "The goal of typography is to relate font size, line height, and line width in a proportional way that maximizes beauty and makes reading easier and more pleasant."
        ),
        style={
            "background": "var(--gray-a2)",
            "border": "1px dashed var(--gray-a7)",
        },
        padding="16px",
    ),
    direction="column",
    spacing="3",
)
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.heading(
        "The quick brown fox jumps over the lazy dog.", as_="h2", color_scheme="indigo"
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.", as_="h2", color_scheme="cyan"
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.", as_="h2", color_scheme="crimson"
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.", as_="h2", color_scheme="orange"
    ),
    direction="column",
)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.heading(
        "The quick brown fox jumps over the lazy dog.",
        as_="h2",
        color_scheme="indigo",
        high_contrast=True,
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.",
        as_="h2",
        color_scheme="cyan",
        high_contrast=True,
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.",
        as_="h2",
        color_scheme="crimson",
        high_contrast=True,
    ),
    rx.heading(
        "The quick brown fox jumps over the lazy dog.",
        as_="h2",
        color_scheme="orange",
        high_contrast=True,
    ),
    direction="column",
)
```
