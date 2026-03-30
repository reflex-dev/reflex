```python exec
import reflex as rx
```

# Setters

Every base var has a built-in event handler to set it's value for convenience, called `set_VARNAME`.

Say you wanted to change the value of the select component. You could write your own event handler to do this:

```python demo exec

options: list[str] = ["1", "2", "3", "4"]
class SetterState1(rx.State):
    selected: str = "1"

    @rx.event
    def change(self, value):
        self.selected = value


def code_setter():
    return rx.vstack(
        rx.badge(SetterState1.selected, color_scheme="green"),
        rx.select(
            options,
            on_change= lambda value: SetterState1.change(value),
        )
    )

```

Or you could could use a built-in setter for conciseness.

```python demo exec

options: list[str] = ["1", "2", "3", "4"]
class SetterState2(rx.State):
    selected: str = "1"

    @rx.event
    def set_selected(self, selected: str):
        self.selected = selected

def code_setter_2():
    return rx.vstack(
        rx.badge(SetterState2.selected, color_scheme="green"),
        rx.select(
            options,
            on_change= SetterState2.set_selected,
        )
    )
```

In this example, the setter for `selected` is `set_selected`. Both of these examples are equivalent.

Setters are a great way to make your code more concise. But if you want to do something more complicated, you can always write your own function in the state.
