---
components:
    - rx.chakra.Spacer
---

# Spacer

```python exec
import reflex as rx
```

Creates an adjustable, empty space that can be used to tune the spacing between child elements within Flex.

```python demo
rx.chakra.flex(
    rx.chakra.center(rx.chakra.text("Example"), bg="lightblue"),
    rx.chakra.spacer(),
    rx.chakra.center(rx.chakra.text("Example"), bg="lightgreen"),
    rx.chakra.spacer(),
    rx.chakra.center(rx.chakra.text("Example"), bg="salmon"),
    width="100%",
)
```
