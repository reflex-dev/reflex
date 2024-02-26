```python exec
import random
import time

import reflex as rx
```

# Computed Vars

Computed vars have values derived from other properties on the backend. They are
defined as methods in your State class with the `@rx.var` decorator. A computed
var is recomputed whenever an event is processed against the state.

Try typing in the input box and clicking out.

```python demo exec
class UppercaseState(rx.State):
    text: str = "hello"

    @rx.var
    def upper_text(self) -> str:
        # This will be recomputed whenever `text` changes.
        return self.text.upper()


def uppercase_example():
    return rx.vstack(
        rx.heading(UppercaseState.upper_text),
        rx.chakra.input(on_blur=UppercaseState.set_text, placeholder="Type here..."),
    )
```

Here, `upper_text` is a computed var that always holds the upper case version of `text`.

We recommend always using type annotations for computed vars.

## Cached Vars

A cached var, decorated as `@rx.cached_var` is a special type of computed var
that is only recomputed when the other state vars it depends on change. This is
useful for expensive computations, but in some cases it may not update when you
expect it to.

```python demo exec
class CachedVarState(rx.State):
    counter_a: int = 0
    counter_b: int = 0

    @rx.var
    def last_touch_time(self) -> str:
        # This is updated anytime the state is updated.
        return time.strftime("%H:%M:%S")

    def increment_a(self):
        self.counter_a += 1

    @rx.cached_var
    def last_counter_a_update(self) -> str:
        # This is updated only when `counter_a` changes.
        return f"{self.counter_a} at {time.strftime('%H:%M:%S')}"

    def increment_b(self):
        self.counter_b += 1

    @rx.cached_var
    def last_counter_b_update(self) -> str:
        # This is updated only when `counter_b` changes.
        return f"{self.counter_b} at {time.strftime('%H:%M:%S')}"


def cached_var_example():
    return rx.vstack(
        rx.text(f"State touched at: {CachedVarState.last_touch_time}"),
        rx.text(f"Counter A: {CachedVarState.last_counter_a_update}"),
        rx.text(f"Counter B: {CachedVarState.last_counter_b_update}"),
        rx.hstack(
            rx.button("Increment A", on_click=CachedVarState.increment_a),
            rx.button("Increment B", on_click=CachedVarState.increment_b),
        ),
    )
```

In this example `last_touch_time` is a normal computed var, which updates any
time the state is modified. `last_counter_a_update` is a computed var that only
depends on `counter_a`, so it only gets recomputed when `counter_a` has changes.
Similarly `last_counter_b_update` only depends on `counter_b`, and thus is
updated only when `counter_b` changes.
