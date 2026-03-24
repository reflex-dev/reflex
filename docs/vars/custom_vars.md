```python exec
import reflex as rx
import dataclasses
from typing import TypedDict

from pcweb.pages.docs import vars
```

# Custom Vars

As mentioned in the [vars page]({vars.base_vars.path}), Reflex vars must be JSON serializable.

This means we can support any Python primitive types, as well as lists, dicts, and tuples. However, you can also create more complex var types using dataclasses (recommended), TypedDict, or Pydantic models.

## Defining a Type

In this example, we will create a custom var type for storing translations using a dataclass.

Once defined, we can use it as a state var, and reference it from within a component.

```python demo exec
import googletrans
import dataclasses
from typing import TypedDict

@dataclasses.dataclass
class Translation:
    original_text: str
    translated_text: str

class TranslationState(rx.State):
    input_text: str = "Hola Mundo"
    current_translation: Translation = Translation(original_text="", translated_text="")

    # Explicitly define the setter method
    def set_input_text(self, value: str):
        self.input_text = value

    @rx.event
    def translate(self):
        self.current_translation.original_text = self.input_text
        self.current_translation.translated_text = googletrans.Translator().translate(self.input_text, dest="en").text

def translation_example():
    return rx.vstack(
        rx.input(
            on_blur=TranslationState.set_input_text,
            default_value=TranslationState.input_text,
            placeholder="Text to translate...",
        ),
        rx.button("Translate", on_click=TranslationState.translate),
        rx.text(TranslationState.current_translation.translated_text),
    )
```

## Alternative Approaches

### Using TypedDict

You can also use TypedDict for defining custom var types:

```python
from typing import TypedDict

class Translation(TypedDict):
    original_text: str
    translated_text: str
```

### Using Pydantic Models

Pydantic models are another option for complex data structures:

```python
from pydantic import BaseModel

class Translation(BaseModel):
    original_text: str
    translated_text: str
```

For complex data structures, dataclasses are recommended as they provide a clean, type-safe way to define custom var types with good IDE support.
