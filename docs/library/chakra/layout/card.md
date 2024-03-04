---
components:
    - rx.chakra.Card
    - rx.chakra.CardHeader
    - rx.chakra.CardBody
    - rx.chakra.CardFooter
---

```python exec
import reflex as rx
```

# Card

Card is a flexible component used to group and display content in a clear and concise format.

```python demo
rx.chakra.card(
    rx.chakra.text("Body of the Card Component"), 
    header=rx.chakra.heading("Header", size="lg"), 
    footer=rx.chakra.heading("Footer",size="sm"),
)
```

You can pass a header with `header=` and/or a footer with `footer=`.
