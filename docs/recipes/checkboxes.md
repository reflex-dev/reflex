```python exec
import reflex as rx
```

# Smart Checkboxes Group

A smart checkboxes group where you can track all checked boxes, as well as place a limit on how many checks are possible.

## Recipe

```python eval
rx.center(rx.image(src="/gallery/smart_checkboxes.gif"))
```

This recipe use a `dict[str, bool]` for the checkboxes state tracking.
Additionally, the limit that prevent the user from checking more boxes than allowed with a computed var.

```python
class CBoxeState(rx.State):
    
    choices: dict[str, bool] = \{k: False for k in ["Choice A", "Choice B", "Choice C"]}
    _check_limit = 2

    def check_choice(self, value, index):
        self.choices[index] = value

    @rx.var
    def choice_limit(self):
        return sum(self.choices.values()) >= self._check_limit

    @rx.var
    def checked_choices(self):
        choices = [l for l, v in self.choices.items() if v]
        return " / ".join(choices) if choices else "None"

import reflex as rx


def render_checkboxes(values, limit, handler):
    return rx.vstack(
            rx.foreach(
                values,
                lambda choice: rx.checkbox(
                    choice[0],
                    checked=choice[1],
                    disabled=~choice[1] & limit,
                    on_change=lambda val: handler(val, choice[0]),
                ),
            )
    )


def index() -> rx.Component:
    
    return rx.center(
        rx.vstack(
            rx.text("Make your choices (2 max):"),
            render_checkboxes(
                CBoxeState.choices,
                CBoxeState.choice_limit,
                CBoxeState.check_choice,
            ),
            rx.text("Your choices: ", CBoxeState.checked_choices),
        ),
        height="100vh",
    )
```
