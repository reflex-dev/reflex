---
components:
  - rx.grid

Grid: |
  lambda **props: rx.grid(
      rx.card("Card 1", size="2", width="5rem"),
      rx.card("Card 2", size="2", width="5rem"),
      rx.card("Card 3", size="2", width="5rem"),
      rx.card("Card 4", size="2", width="5rem"),
      rx.card("Card 5", size="2", width="5rem"),
      rx.card("Card 6", size="2", width="5rem"),
      columns="3",
      gap="0.75rem",
      width="100%",
      min_height="10rem",
      border="1px dashed var(--gray-7)",
      border_radius="0.5rem",
      padding="0.75rem",
      **props,
  )
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
