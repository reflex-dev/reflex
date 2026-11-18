---
components:
  - rx.button

Button: |
  lambda **props: rx.button("Basic Button", **props)
---

```python exec
import reflex as rx
```

# Button

Buttons are essential elements in your application's user interface that users can click to trigger events.

## Basic Example

The `on_click` trigger is called when the button is clicked.

```python demo exec
class CountState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1


def counter():
    return rx.flex(
        rx.button(
            "Decrement",
            color_scheme="red",
            on_click=CountState.decrement,
        ),
        rx.heading(CountState.count, as_="h2"),
        rx.button(
            "Increment",
            color_scheme="grass",
            on_click=CountState.increment,
        ),
        spacing="3",
    )
```

```python test
def test_button_counter(demo):
    count = demo.get_by_role("heading")
    expect(count).to_have_text("0")
    demo.get_by_role("button", name="Increment").click()
    demo.get_by_role("button", name="Increment").click()
    expect(count).to_have_text("2")
    demo.get_by_role("button", name="Decrement").click()
    expect(count).to_have_text("1")
```

### Loading and Disabled

The `loading` prop is used to indicate that the action triggered by the button is currently in progress. When set to `True`, the button displays a loading spinner, providing visual feedback to the user that the action is being processed. This also prevents multiple clicks while the button is in the loading state. By default, `loading` is set to `False`.

The `disabled` prop also prevents the button from being but does not provide a spinner.

```python demo
rx.flex(
    rx.button("Regular"),
    rx.button("Loading", loading=True),
    rx.button("Disabled", disabled=True),
    spacing="2",
)
```

```python test
def test_button_loading_and_disabled(demo):
    expect(demo.get_by_role("button")).to_have_count(3)
    expect(demo.get_by_role("button", name="Regular")).to_be_enabled()
    expect(demo.get_by_role("button", name="Loading")).to_be_disabled()
    expect(demo.get_by_role("button", name="Disabled")).to_be_disabled()
```
