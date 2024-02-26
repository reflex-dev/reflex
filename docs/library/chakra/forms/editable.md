---
components:
    - rx.chakra.Editable
    - rx.chakra.EditablePreview
    - rx.chakra.EditableInput
    - rx.chakra.EditableTextarea
---

```python exec
import reflex as rx
```

# Editable

Editable is used for inline renaming of some text.
It appears as normal UI text but transforms into a text input field when the user clicks on or focuses it.

```python demo exec
class EditableState(rx.State):
    example_input: str
    example_textarea: str
    example_state: str

    def set_uppertext(self, example_state: str):
        self.example_state = example_state.upper()


def editable_example():
    return rx.chakra.editable(
        rx.chakra.editable_preview(),
        rx.chakra.editable_input(),
        placeholder="An input example...",
        on_submit=EditableState.set_uppertext,
        width="100%",
    )
```

Another variant of editable can be made with a textarea instead of an input.

```python demo
rx.chakra.editable(
    rx.chakra.editable_preview(),
    rx.chakra.editable_textarea(),
    placeholder="A textarea example...",
    on_submit=EditableState.set_example_textarea,
    width="100%",
)
```
