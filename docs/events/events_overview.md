```python exec
import reflex as rx

from pcweb.pages.docs.library import library
```

# Events Overview

Events are how we modify the state and make the app interactive.

Event triggers are component props that create an event to be sent to an event handler.
Each component supports a set of events triggers. They are described in each [component's documentation]({library.path}) in the event trigger section.

Lets take a look at an example below. Try mousing over the heading to change the word.

```python demo exec
class WordCycleState(rx.State):
    # The words to cycle through.
    text: list[str] = ["Welcome", "to", "Reflex", "!"]

    # The index of the current word.
    index: int = 0

    def next_word(self):
        self.index = (self.index + 1) % len(self.text)

    @rx.var
    def get_text(self) -> str:
        return self.text[self.index]

def event_triggers_example():
    return rx.heading(
        WordCycleState.get_text,
        on_mouse_over=WordCycleState.next_word,
        color="green",
    )

```

In this example, the heading component has the event trigger, `on_mouse_over`.
Whenever the user hovers over the heading, the `next_word` handler will be called to cycle the word. Once the handler returns, the UI will be updated to reflect the new state.
