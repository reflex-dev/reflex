---
components:
    - rx.chakra.Container
---

# Container

```python exec
import reflex as rx
```

Containers are used to constrain a content's width to the current breakpoint, while keeping it fluid.

```python demo
rx.chakra.container(
    rx.chakra.box("Example", bg="blue", color="white", width="50%"),
    center_content=True,
    bg="lightblue",
)
```
