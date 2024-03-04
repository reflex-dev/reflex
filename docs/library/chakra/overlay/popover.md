---
components:
    - rx.chakra.Popover
    - rx.chakra.PopoverTrigger
    - rx.chakra.PopoverContent
    - rx.chakra.PopoverHeader
    - rx.chakra.PopoverBody
    - rx.chakra.PopoverFooter
    - rx.chakra.PopoverArrow
    - rx.chakra.PopoverAnchor
---

```python exec
import reflex as rx
```

# Popover

Popover is a non-modal dialog that floats around a trigger.
It is used to display contextual information to the user, and should be paired with a clickable trigger element.

```python demo
rx.chakra.popover(
    rx.chakra.popover_trigger(rx.chakra.button("Popover Example")),
    rx.chakra.popover_content(
        rx.chakra.popover_header("Confirm"),
        rx.chakra.popover_body("Do you want to confirm example?"),
        rx.chakra.popover_footer(rx.chakra.text("Footer text.")),
        rx.chakra.popover_close_button(),
    ),
)
```
