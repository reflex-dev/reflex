---
components:
  - rx.center

Center: |
  lambda **props: rx.center(
      rx.card("Card 1", size="2"),
      rx.card("Card 2", size="2"),
      rx.card("Card 3", size="2"),
      gap="0.75rem",
      width="100%",
      height="10rem",
      border_radius="0.5rem",
      **props,
  )
---

```python exec
import reflex as rx
```

# Center

`Center` is a component that centers its children within itself. It is based on the `flex` component and therefore inherits all of its props.

```python demo
rx.center(
    rx.text("Hello World!"),
    border_radius="15px",
    border_width="thick",
    width="50%",
)
```
