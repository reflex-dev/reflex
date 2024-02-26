---
components:
    - rx.debounce_input
---

```python exec
import reflex as rx
```

# Debounce

Reflex is a backend-centric framework, which can create negative performance impacts for apps that need to provide interactive feedback to the user in real time. For example, if a search bar sends a request to the backend on every keystroke, it may result in a laggy UI. This is because the backend is doing a lot of work to process each keystroke, and the frontend is waiting for the backend to respond before updating the UI.

Using the `rx.debounce_input`  component allows the frontend to remain responsive while receiving user input and sends the value to the backend after some delay, on blur, or when `Enter` is pressed.

"Typically, this component is used to wrap a child `rx.chakra.input` or `rx.text_area`, however, most child components that accept the `value` prop and `on_change` event handler can be used with `rx.debounce_input`."

This example only sends the final checkbox state to the backend after a 1 second delay.

```python demo exec
class DebounceCheckboxState(rx.State):
    checked: bool = False

def debounce_checkbox_example():
    return rx.hstack(
        rx.cond(
            DebounceCheckboxState.checked,
            rx.text("Checked", color="green"),
            rx.text("Unchecked", color="red"),
        ),
        rx.debounce_input(
            rx.chakra.checkbox(
                on_change=DebounceCheckboxState.set_checked,
            ),
            debounce_timeout=1000,
        ),
    )
```
