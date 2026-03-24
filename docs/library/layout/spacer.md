---
components:
    - rx.spacer
---

```python exec
import reflex as rx
```

# Spacer

Creates an adjustable, empty space that can be used to tune the spacing between child elements within `flex`.

```python demo
rx.flex(
    rx.center(rx.text("Example"), bg="lightblue"),
    rx.spacer(),
    rx.center(rx.text("Example"), bg="lightgreen"),
    rx.spacer(),
    rx.center(rx.text("Example"), bg="salmon"),
    width="100%",
)
```

As `stack`, `vstack` and `hstack` are all built from `flex`, it is possible to also use `spacer` inside of these components.
