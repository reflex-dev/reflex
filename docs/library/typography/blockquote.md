---
components:
    - rx.blockquote
---

```python exec
import reflex as rx
```

# Blockquote

```python demo
rx.blockquote("Perfect typography is certainly the most elusive of all arts.")
```

## Size

Use the `size` prop to control the size of the blockquote. The prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="1"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="2"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="3"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="4"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="5"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="6"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="7"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="8"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", size="9"),
    direction="column",
    spacing="3",
)
```

## Weight

Use the `weight` prop to set the blockquote weight.

```python demo
rx.flex(
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", weight="light"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", weight="regular"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", weight="medium"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", weight="bold"),
    direction="column",
    spacing="3",
)
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", color_scheme="indigo"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", color_scheme="cyan"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", color_scheme="crimson"),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", color_scheme="orange"),
    direction="column",
    spacing="3",
)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.blockquote("Perfect typography is certainly the most elusive of all arts."),
    rx.blockquote("Perfect typography is certainly the most elusive of all arts.", high_contrast=True),
    direction="column",
    spacing="3",
)
```
