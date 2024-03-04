---
components:
    - rx.chakra.Select
---

```python exec
import reflex as rx
```

# Select

The Select component is used to create a list of options, which allows a user to select one or more options from it.

```python demo exec
from typing import List
options: List[str] = ["Option 1", "Option 2", "Option 3"]

class SelectState(rx.State):
    option: str = "No selection yet."


def basic_select_example():
    return rx.chakra.vstack(
        rx.chakra.heading(SelectState.option),
        rx.chakra.select(
            options,
            placeholder="Select an example.",
            on_change=SelectState.set_option,
            color_schemes="twitter",
        ),
    )
```

Select can also have multiple options selected at once.

```python demo exec
from typing import List
options: List[str] = ["Option 1", "Option 2", "Option 3"]

class MultiSelectState(rx.State):
    option: List[str] = []


def multiselect_example():
    return rx.chakra.vstack(
        rx.chakra.heading(MultiSelectState.option),
        rx.chakra.select(
            options, 
            placeholder="Select examples", 
            is_multi=True,
            on_change=MultiSelectState.set_option,
            close_menu_on_select=False,
            color_schemes="twitter",
        ),
    )
```

The component can also be customized and styled as seen in the next examples.

```python demo
rx.chakra.vstack(
    rx.chakra.select(options, placeholder="Select an example.", size="xs"),
    rx.chakra.select(options, placeholder="Select an example.", size="sm"),
    rx.chakra.select(options, placeholder="Select an example.", size="md"),
    rx.chakra.select(options, placeholder="Select an example.", size="lg"),
)
```

```python demo
rx.chakra.vstack(
    rx.chakra.select(options, placeholder="Select an example.", variant="outline"),
    rx.chakra.select(options, placeholder="Select an example.", variant="filled"),
    rx.chakra.select(options, placeholder="Select an example.", variant="flushed"),
    rx.chakra.select(options, placeholder="Select an example.", variant="unstyled"),
)
```

```python demo
rx.chakra.select(
    options,
    placeholder="Select an example.",
    color="white",
    bg="#68D391",
    border_color="#38A169",
)
```
