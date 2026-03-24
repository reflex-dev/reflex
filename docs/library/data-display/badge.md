---
components:
    - rx.badge

Badge: |
    lambda **props: rx.badge("Basic Badge", **props)
---
# Badge

```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
```

Badges are used to highlight an item's status for quick recognition.

## Basic Example

To create a badge component with only text inside, pass the text as an argument.

```python demo
rx.badge("New")
```

## Styling

```python eval
style_grid(component_used=rx.badge, component_used_str="rx.badge", variants=["solid", "soft", "surface", "outline"], components_passed="England!",)
```

### Size

The `size` prop controls the size and padding of a badge. It can take values of `"1" | "2"`, with default being `"1"`.

```python demo
rx.flex(
    rx.badge("New"),
    rx.badge("New", size="1"),
    rx.badge("New", size="2"),
    align="center",
    spacing="2",
)
```

### Variant

The `variant` prop controls the visual style of the badge. The supported variant types are `"solid" | "soft" | "surface" | "outline"`. The variant default is `"soft"`.

```python demo
rx.flex(
    rx.badge("New", variant="solid"),
    rx.badge("New", variant="soft"),
    rx.badge("New"),
    rx.badge("New", variant="surface"),
    rx.badge("New", variant="outline"),
    spacing="2",
)
```

### Color Scheme

The `color_scheme` prop sets a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.badge("New", color_scheme="indigo"),
    rx.badge("New", color_scheme="cyan"),
    rx.badge("New", color_scheme="orange"),
    rx.badge("New", color_scheme="crimson"),
    spacing="2",
)
```

### High Contrast

The `high_contrast` prop increases color contrast of the fallback text with the background.

```python demo
rx.flex(
    rx.flex(
        rx.badge("New", variant="solid"),
        rx.badge("New", variant="soft"),
        rx.badge("New", variant="surface"),
        rx.badge("New", variant="outline"),
        spacing="2",
    ),
    rx.flex(
        rx.badge("New", variant="solid", high_contrast=True),
        rx.badge("New", variant="soft", high_contrast=True),
        rx.badge("New", variant="surface", high_contrast=True),
        rx.badge("New", variant="outline", high_contrast=True),
        spacing="2",
    ),
    direction="column",
    spacing="2",
)
```

### Radius

The `radius` prop sets specific radius value, ignoring the global theme. It can take values `"none" | "small" | "medium" | "large" | "full"`.

```python demo
rx.flex(
    rx.badge("New", radius="none"),
    rx.badge("New", radius="small"),
    rx.badge("New", radius="medium"),
    rx.badge("New", radius="large"),
    rx.badge("New", radius="full"),
    spacing="3",
)
```

## Final Example

A badge may contain more complex elements within it. This example uses a `flex` component to align an icon and the text correctly, using the `gap` prop to
ensure a comfortable spacing between the two.

```python demo
rx.badge(
    rx.flex(
        rx.icon(tag="arrow_up"),
        rx.text("8.8%"),
        spacing="1",
    ),
    color_scheme="grass",
)
```
