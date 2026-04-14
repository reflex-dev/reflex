---
components:
  - rx.grid
---

```python exec
import reflex as rx
```

# Grid

Component for creating grid layouts. Either `rows` or `columns` may be specified.

## Basic Example

```python demo
rx.grid(
    rx.foreach(
        rx.Var.range(12),
        lambda i: rx.card(f"Card {i + 1}", height="10vh"),
    ),
    columns="3",
    spacing="4",
    width="100%",
)
```

```python demo
rx.grid(
    rx.foreach(
        rx.Var.range(12),
        lambda i: rx.card(f"Card {i + 1}", height="10vh"),
    ),
    rows="3",
    flow="column",
    justify="between",
    spacing="4",
    width="100%",
)
```
