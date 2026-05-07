---
components:
  - rx.section

Section: |
  lambda **props: rx.section(
      rx.text("Section content", color="black"),
      background="white",
      border_radius="0.5rem",
      width="100%",
      justify="center",
      border="1px solid var(--gray-3)",
      align="center",
      display="flex",
      padding="4rem",
      **props,
  )
---

```python exec
import reflex as rx
```

# Section

Denotes a section of page content, providing vertical padding by default.

Primarily this is a semantic component that is used to group related textual content.

## Basic Example

```python demo
rx.box(
    rx.section(
        rx.heading("First"),
        rx.text("This is the first content section"),
        padding_left="12px",
        padding_right="12px",
        background_color="var(--gray-2)",
    ),
    rx.section(
        rx.heading("Second"),
        rx.text("This is the second content section"),
        padding_left="12px",
        padding_right="12px",
        background_color="var(--gray-2)",
    ),
    width="100%",
)
```
