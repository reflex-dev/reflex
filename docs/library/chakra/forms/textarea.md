---
components:
    - rx.chakra.TextArea
---

```python exec
import reflex as rx
from pcweb.pages.docs import library
```

# Textarea

The TextArea component allows you to easily create multi-line text inputs.

```python demo exec
class TextareaState(rx.State):
    text: str = "Hello World!"

def textarea_example():
    return rx.chakra.vstack(
        rx.chakra.heading(TextareaState.text),
        rx.chakra.text_area(value=TextareaState.text, on_change=TextareaState.set_text)
    )
```

Alternatively, you can use the `on_blur` event handler to only update the state when the user clicks away.

Similar to the Input component, the TextArea is also implemented using debounced input when it is fully controlled.
You can tune the debounce delay by setting the `debounce_timeout` prop.
You can find examples of how it is used in the [DebouncedInput]({library.forms.debounce.path}) component.
