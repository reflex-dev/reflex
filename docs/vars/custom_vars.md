```python exec
import reflex as rx
import dataclasses
from typing import TypedDict
```

# Custom Vars

As mentioned in the [vars page](/docs/vars/base_vars), Reflex vars must be JSON serializable.

This means we can support any Python primitive types, as well as lists, dicts, and tuples. However, you can also create more complex var types using dataclasses (recommended), TypedDict, or Pydantic models.

## Defining a Type

In this example, we will create a custom var type for storing a transformed piece of text using a dataclass.

Once defined, we can use it as a state var, and reference it from within a component.

```python demo exec
import dataclasses


@dataclasses.dataclass
class TextEntry:
    original_text: str
    upper_text: str


class TextEntryState(rx.State):
    input_text: str = "hello world"
    current_entry: TextEntry = TextEntry(original_text="", upper_text="")

    # Explicitly define the setter method
    def set_input_text(self, value: str):
        self.input_text = value

    @rx.event
    def transform(self):
        self.current_entry.original_text = self.input_text
        self.current_entry.upper_text = self.input_text.upper()


def text_entry_example():
    return rx.vstack(
        rx.input(
            on_blur=TextEntryState.set_input_text,
            default_value=TextEntryState.input_text,
            placeholder="Text to transform...",
        ),
        rx.button("Transform", on_click=TextEntryState.transform),
        rx.text(TextEntryState.current_entry.upper_text),
    )
```

## Alternative Approaches

### Using TypedDict

You can also use TypedDict for defining custom var types:

```python
from typing import TypedDict


class TextEntry(TypedDict):
    original_text: str
    upper_text: str
```

### Using Pydantic Models

Pydantic models are another option for complex data structures:

```python
from pydantic import BaseModel


class TextEntry(BaseModel):
    original_text: str
    upper_text: str
```

For complex data structures, dataclasses are recommended as they provide a clean, type-safe way to define custom var types with good IDE support.
