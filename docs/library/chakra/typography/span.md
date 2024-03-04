---
components:
    - rx.chakra.span
---

```python exec
import reflex as rx
```

# Span

The span component can be used to style inline text without creating a new line.

```python demo
rx.chakra.box(
    "Write some ",
    rx.chakra.span("stylized ", color="red"),    
    rx.chakra.span("text ", color="blue"),
    rx.chakra.span("using spans.", font_weight="bold")
)
```
