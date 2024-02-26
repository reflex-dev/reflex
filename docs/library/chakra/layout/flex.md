---
components:
    - rx.chakra.Flex
---

# Flex

```python exec
import reflex as rx
```

Flexbox is a layout model that allows elements to align and distribute space within a container. Using flexible widths and heights, elements can be aligned to fill a space or distribute space between elements, which makes it a great tool to use for responsive design systems.

```python demo
rx.chakra.flex(
    rx.chakra.center("Center", bg="lightblue"),
    rx.chakra.square("Square", bg="lightgreen", padding=10),
    rx.chakra.box("Box", bg="salmon", width="150px"),
)
```

Combining flex with spacer allows for stackable and responsive components.

```python demo
rx.chakra.flex(
    rx.chakra.center("Center", bg="lightblue"),
    rx.chakra.spacer(),
    rx.chakra.square("Square", bg="lightgreen", padding=10),
    rx.chakra.spacer(),
    rx.chakra.box("Box", bg="salmon", width="150px"),
    width = "100%",
)
```
