---
components:
    - rx.chakra.ResponsiveGrid
---

# Responsive Grid

```python exec
import reflex as rx
```

ResponsiveGrid provides a friendly interface to create responsive grid layouts with ease. SimpleGrid composes Box so you can pass all the Box props and css grid props with addition to the ones below.

Specify a fixed number of columns for the grid layout.

```python demo
rx.chakra.responsive_grid(
    rx.chakra.box(height="5em", width="5em", bg="lightgreen"),
    rx.chakra.box(height="5em", width="5em", bg="lightblue"),
    rx.chakra.box(height="5em", width="5em", bg="purple"),
    rx.chakra.box(height="5em", width="5em", bg="tomato"),
    rx.chakra.box(height="5em", width="5em", bg="orange"),
    rx.chakra.box(height="5em", width="5em", bg="yellow"),
    columns=[3],
    spacing="4",
)
```

```python demo
rx.chakra.responsive_grid(
    rx.chakra.box(height="5em", width="5em", bg="lightgreen"),
    rx.chakra.box(height="5em", width="5em", bg="lightblue"),
    rx.chakra.box(height="5em", width="5em", bg="purple"),
    rx.chakra.box(height="5em", width="5em", bg="tomato"),
    rx.chakra.box(height="5em", width="5em", bg="orange"),
    rx.chakra.box(height="5em", width="5em", bg="yellow"),
    columns=[1, 2, 3, 4, 5, 6],
)
```
