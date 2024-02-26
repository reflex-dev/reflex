---
components:
    - rx.radix.button

Button: |
    lambda **props: rx.radix.themes.button("Basic Button", **props)
---


```python exec
import reflex as rx
```

# Button

Buttons are essential elements in your application's user interface that users can click to trigger events. This component uses Radix's [button](https://radix-ui.com/primitives/docs/components/button) component.

## Basic Example

```python demo
rx.button("Click me")
```

### With Icon

```python demo
rx.button(
    rx.icon(tag="heart"),
    "Like",
    color_scheme="red",
)
```

## Props

### Disabled

The `disabled` prop disables the button, by default it is `False`.  A disabled button does not respond to user interactions such as click and cannot be focused.

```python demo
rx.flex(
    rx.button("Enabled"),
    rx.button("Disabled", disabled=True),
    spacing="2",
)
```

## Triggers

### On Click

The `on_click` trigger is called when the button is clicked.

```python demo
rx.button("Click me", on_click=rx.window_alert("Clicked!"))
```

## Real World Example

```python demo exec
class CountState(rx.State):
    count: int = 0

    def increment(self):
        self.count += 1

    def decrement(self):
        self.count -= 1

def counter():
    return rx.flex(
        rx.button(
            "Decrement",
            color_scheme="red",
            on_click=CountState.decrement,
        ),
        rx.heading(CountState.count),
        rx.button(
            "Increment",
            color_scheme="grass",
            on_click=CountState.increment,
        ),
        spacing="3",
    )
```
