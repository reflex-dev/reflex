---
title: Number Formatter
---

# Number Formatter component
`rxe.mantine.number_formatter` is a component for formatting numbers in a user-friendly way. It allows you to specify the format, precision, and other options for displaying numbers.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def number_formatter_example():
    return rx.vstack(
        rxe.mantine.number_formatter(
            value=100,
            prefix="$",
        ),
        rxe.mantine.number_formatter(
            value=100,
            suffix="€",
        ),
        rxe.mantine.number_formatter(
            value=1234567.89,
            thousand_separator=True,
        ),
    )
```
