---
components:
    - rx.chakra.Divider
---

```python exec
import reflex as rx
```

# Divider

Dividers are a quick built in way to separate sections of content.

```python demo
rx.chakra.vstack(
    rx.chakra.text("Example"),
    rx.chakra.divider(border_color="black"),
    rx.chakra.text("Example"),
    rx.chakra.divider(variant="dashed", border_color="black"),
    width="100%",
)
```

If the vertical orientation is used, make sure that the parent component is assigned a height.

```python demo
rx.chakra.center(
    rx.chakra.divider(
        orientation="vertical", 
        border_color = "black"
    ), 
    height = "4em"
)
```
