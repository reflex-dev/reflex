---
components:
    - rx.chakra.Checkbox
---

# Checkbox

A checkbox is a common way to toggle boolean value.
The checkbox component can be used on its own or in a group.

```python exec
import reflex as rx
```

```python demo
rx.chakra.checkbox("Check Me!")
```

Checkboxes can range in size and styles.

```python demo
rx.chakra.hstack(
    rx.chakra.checkbox("Example", color_scheme="green", size="sm"),
    rx.chakra.checkbox("Example", color_scheme="blue", size="sm"),
    rx.chakra.checkbox("Example", color_scheme="yellow", size="md"),
    rx.chakra.checkbox("Example", color_scheme="orange", size="md"),
    rx.chakra.checkbox("Example", color_scheme="red", size="lg"),
)
```

Checkboxes can also have different visual states.

```python demo
rx.chakra.hstack(
    rx.chakra.checkbox(
        "Example", color_scheme="green", size="lg", is_invalid=True
    ),
    rx.chakra.checkbox(
        "Example", color_scheme="green", size="lg", is_disabled=True
    ),
)
```

Checkboxes can be hooked up to a state using the `on_change` prop.

```python demo exec
import reflex as rx


class CheckboxState(rx.State):
    checked: bool = False

    def toggle(self):
        self.checked = not self.checked


def checkbox_state_example():
    return rx.chakra.hstack(
        rx.cond(
            CheckboxState.checked,
            rx.chakra.text("Checked", color="green"),
            rx.chakra.text("Unchecked", color="red"),
        ),
        rx.chakra.checkbox(
            "Example",
            on_change=CheckboxState.set_checked,
        )
    )
```
