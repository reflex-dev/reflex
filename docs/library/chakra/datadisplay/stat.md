---
components:
    - rx.chakra.Stat
    - rx.chakra.StatLabel
    - rx.chakra.StatNumber
    - rx.chakra.StatHelpText
    - rx.chakra.StatArrow
    - rx.chakra.StatGroup
---

```python exec
import reflex as rx
```

# Stat

The stat component is a great way to visualize statistics in a clean and concise way.

```python demo
rx.chakra.stat(
    rx.chakra.stat_label("Example Price"),
    rx.chakra.stat_number("$25"),
    rx.chakra.stat_help_text("The price of the item."),
)
```

Example of a stats in a group with arrow.

```python demo
rx.chakra.stat_group(
        rx.chakra.stat(
            rx.chakra.stat_number("$250"),
            rx.chakra.stat_help_text("%50", rx.chakra.stat_arrow(type_="increase")),
        ),
        rx.chakra.stat(
            rx.chakra.stat_number("£100"),
            rx.chakra.stat_help_text("%50", rx.chakra.stat_arrow(type_="decrease")),
        ),
        width="100%",
)
```
