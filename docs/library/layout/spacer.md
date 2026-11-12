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
    rx.center(rx.text("Example"), bg="lightblue", color="black"),
    rx.spacer(),
    rx.center(rx.text("Example"), bg="lightgreen", color="black"),
    rx.spacer(),
    rx.center(rx.text("Example"), bg="salmon", color="black"),
    width="100%",
)
```

As `stack`, `vstack` and `hstack` are all built from `flex`, it is possible to also use `spacer` inside of these components.
