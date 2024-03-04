---
components:
    - rx.chakra.Heading
---

```python exec
import reflex as rx
```

# Heading

The Heading component takes in a string and displays it as a heading.

```python demo
rx.chakra.heading("Hello World!")
```

The size can be changed using the `size` prop.

```python demo
rx.chakra.vstack(
    rx.chakra.heading("Hello World!", size= "sm", color="red"),
    rx.chakra.heading("Hello World!", size= "md", color="blue"),
    rx.chakra.heading("Hello World!", size= "lg", color="green"),
    rx.chakra.heading("Hello World!", size= "xl", color="blue"),
    rx.chakra.heading("Hello World!", size= "2xl", color="red"),
    rx.chakra.heading("Hello World!", size= "3xl", color="blue"),
    rx.chakra.heading("Hello World!", size= "4xl", color="green"),
)
```

It can also be styled using regular CSS styles.

```python demo
rx.chakra.heading("Hello World!", font_size="2em")
```
