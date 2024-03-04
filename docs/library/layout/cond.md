---
components:
    - rx.components.core.Cond
---

```python exec
import reflex as rx
```

# Cond

This component is used to conditionally render components.

The cond component takes a condition and two components.
If the condition is `True`, the first component is rendered, otherwise the second component is rendered.

```python demo exec
class CondState(rx.State):
    show: bool = True

    def change(self):
        self.show = not (self.show)


def cond_example():
    return rx.vstack(
        rx.button("Toggle", on_click=CondState.change),
        rx.cond(CondState.show, rx.text("Text 1", color="blue"), rx.text("Text 2", color="red")),
    )
```

The second component is optional and can be omitted.
If it is omitted, nothing is rendered if the condition is `False`.

## Negation

You can use the logical operator `~` to negate a condition.

```python
rx.vstack(
    rx.button("Toggle", on_click=CondState.change),
    rx.cond(CondState.show, rx.text("Text 1", color="blue"), rx.text("Text 2", color="red")),
    rx.cond(~CondState.show, rx.text("Text 1", color="blue"), rx.text("Text 2", color="red")),
)
```

## Multiple Conditions

You can use the logical operators `&` and `|` to combine multiple conditions.

```python demo exec
class MultiCondState(rx.State):
    cond1: bool = True
    cond2: bool = False
    cond3: bool = True

    def change(self):
        self.cond1 = not (self.cond1)


def multi_cond_example():
    return rx.vstack(
        rx.button("Toggle", on_click=MultiCondState.change),
        rx.text(
            rx.cond(MultiCondState.cond1, "True", "False"), 
            " & True => ", 
            rx.cond(MultiCondState.cond1 & MultiCondState.cond3, "True", "False"),
        ),
        rx.text(
            rx.cond(MultiCondState.cond1, "True", "False"), 
            " & False => ", 
            rx.cond(MultiCondState.cond1 & MultiCondState.cond2, "True", "False"),
        ),  
        rx.text(
            rx.cond(MultiCondState.cond1, "True", "False"), 
            " | False => ", 
            rx.cond(MultiCondState.cond1 | MultiCondState.cond2, "True", "False"),
        ),
    )
```
