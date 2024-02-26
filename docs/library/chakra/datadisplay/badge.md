---
components:
    - rx.chakra.Badge
---

```python exec
import reflex as rx
```

# Badge

Badges are used to highlight an item's status for quick recognition.

There are 3 variants of badges: `solid`, `subtle`, and `outline`.

```python demo
rx.chakra.hstack(
    rx.chakra.badge("Example", variant="solid", color_scheme="green"),
    rx.chakra.badge("Example", variant="subtle", color_scheme="green"),
    rx.chakra.badge("Example", variant="outline", color_scheme="green"),
)
```

Color schemes are an easy way to change the color of a badge.

```python demo
rx.chakra.hstack(
    rx.chakra.badge("Example", variant="subtle", color_scheme="green"),
    rx.chakra.badge("Example", variant="subtle", color_scheme="red"),
    rx.chakra.badge("Example", variant="subtle", color_scheme="yellow"),
)
```

You can also customize the badge through traditional style args.

```python demo
rx.chakra.badge(
    "Custom Badge", 
    bg="#90EE90",
    color="#3B7A57",
    border_color="#29AB87",
    border_width=2
)
```
