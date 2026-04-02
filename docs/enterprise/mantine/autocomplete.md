---
title: Autocomplete
---

# Autocomplete component

`rxe.mantine.autocomplete` is a component for providing suggestions as the user types. It is useful for enhancing user experience by offering relevant options based on input.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def autocomplete_example():
    return rx.vstack(
        rxe.mantine.autocomplete(
            data=["Apple", "Banana", "Cherry", "Date", "Elderberry"],
            placeholder="Type a fruit",
            label="Fruit Autocomplete",
            description="Select a fruit from the list",
        ),
    )
```
