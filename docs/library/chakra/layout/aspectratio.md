---
components:
    - rx.chakra.AspectRatio
---

# Aspect Ratio

```python exec
import reflex as rx
```

Preserve the ratio of the components contained within a region.

```python demo
rx.chakra.box(element="iframe", src="https://bit.ly/naruto-sage", border_color="red")
```

```python demo
rx.chakra.aspect_ratio(
    rx.chakra.box(
        element="iframe",
        src="https://bit.ly/naruto-sage",
        border_color="red"
    ),
    ratio=4/3
)
```
