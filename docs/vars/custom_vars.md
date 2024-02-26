```python exec
import reflex as rx

from pcweb.pages.docs import vars
```

# Custom Vars

As mentioned in the [vars page]({vars.base_vars.path}), Reflex vars must be JSON serializable.

This means we can support any Python primitive types, as well as lists, dicts, and tuples. However, you can also create more complex var types by inheriting from `rx.Base`.

## Defining a Type

In this example, we will create a custom var type for storing translations.

Once defined, we can use it as a state var, and reference it from within a component.

```python demo exec
import googletrans

class Translation(rx.Base):
    original_text: str
    translated_text: str

class TranslationState(rx.State):
    input_text: str = "Hola Mundo"
    current_translation: Translation = Translation(original_text="", translated_text="")

    def translate(self):
        text = googletrans.Translator().translate(self.input_text, dest="en").text
        self.current_translation = Translation(original_text=self.input_text, translated_text=text)


def translation_example():
    return rx.vstack(
        rx.chakra.input(on_blur=TranslationState.set_input_text, default_value=TranslationState.input_text, placeholder="Text to translate..."),
        rx.button("Translate", on_click=TranslationState.translate),
        rx.text(TranslationState.current_translation.translated_text),
    )
```
