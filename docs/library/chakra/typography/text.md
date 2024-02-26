---
components:
    - rx.chakra.Text
---

```python exec
import reflex as rx
```

# Text

The text component displays a paragraph of text.

```python demo
rx.chakra.text("Hello World!", font_size="2em")
```

The text element can be visually modified using the `as_` prop.

```python demo
rx.chakra.vstack(
    rx.chakra.text("Hello World!", as_="i"),
    rx.chakra.text("Hello World!", as_="s"),
    rx.chakra.text("Hello World!", as_="mark"),
    rx.chakra.text("Hello World!", as_="sub"),
)
```
