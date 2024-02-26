---
components:
    - rx.radix.tooltip

Tooltip: |
    lambda **props: rx.radix.themes.tooltip(
        rx.radix.themes.button("Hover over me"),
        content="This is the tooltip content.",
        **props,
    )
---

```python exec
import reflex as rx
```

# Tooltip

A `tooltip` displays informative information when users hover over or focus on an element.

It takes a `content` prop, which is the content associated with the tooltip.

```python demo
rx.tooltip(
    rx.button("Hover over me"),
    content="This is the tooltip content.",
)
```
