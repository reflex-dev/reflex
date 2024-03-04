```python exec
import random
import time

import reflex as rx

from pcweb.pages.docs import vars
```

# Base Vars

Vars are any fields in your app that may change over time. A Var is directly
rendered into the frontend of the app.

Base vars are defined as fields in your State class.

They can have a preset default value. If you don't provide a default value, you
must provide a type annotation.

```md alert warning
# State Vars should provide type annotations.
Reflex relies on type annotations to determine the type of state vars during the compilation process.
```

```python demo exec
class TickerState(rx.State):
    ticker: str ="AAPL"
    price: str = "$150"


def ticker_example():
    return rx.chakra.stat_group(
        rx.chakra.stat(
            rx.chakra.stat_label(TickerState.ticker),
            rx.chakra.stat_number(TickerState.price),
            rx.chakra.stat_help_text(
                rx.chakra.stat_arrow(type_="increase"),
                "4%",
            ),
        ),
    )
```

In this example `ticker` and `price` are base vars in the app, which can be modified at runtime.

```md alert warning
# Vars must be JSON serializable.
Vars are used to communicate between the frontend and backend. They must be primitive Python types, Plotly figures, Pandas dataframes, or [a custom defined type]({vars.custom_vars.path}).
```

## Backend-only Vars

Any Var in a state class that starts with an underscore is considered backend
only and will not be syncronized with the frontend. Data associated with a
specific session that is not directly rendered on the frontend should be stored
in a backend-only var to reduce network traffic and improve performance.

They have the advantage that they don't need to be JSON serializable, however
they must still be cloudpickle-able to be used with redis in prod mode. They are
not directly renderable on the frontend, and may be used to store sensitive
values that should not be sent to the client.

For example, a backend-only var is used to store a large data structure which is
then paged to the frontend using cached vars.

```python demo exec
import numpy as np


class BackendVarState(rx.State):
    _backend: np.ndarray = np.array([random.randint(0, 100) for _ in range(100)])
    offset: int = 0
    limit: int = 10

    @rx.cached_var
    def page(self) -> list[int]:
        return [
            int(x)  # explicit cast to int
            for x in self._backend[self.offset : self.offset + self.limit]
        ]

    @rx.cached_var
    def page_number(self) -> int:
        return (self.offset // self.limit) + 1 + (1 if self.offset % self.limit else 0)

    @rx.cached_var
    def total_pages(self) -> int:
        return len(self._backend) // self.limit + (1 if len(self._backend) % self.limit else 0)

    def prev_page(self):
        self.offset = max(self.offset - self.limit, 0)

    def next_page(self):
        if self.offset + self.limit < len(self._backend):
            self.offset += self.limit

    def generate_more(self):
        self._backend = np.append(self._backend, [random.randint(0, 100) for _ in range(random.randint(0, 100))])


def backend_var_example():
    return rx.vstack(
        rx.hstack(
            rx.button(
                "Prev",
                on_click=BackendVarState.prev_page,
            ),
            rx.text(f"Page {BackendVarState.page_number} / {BackendVarState.total_pages}"),
            rx.button(
                "Next",
                on_click=BackendVarState.next_page,
            ),
            rx.text("Page Size"),
            rx.chakra.number_input(
                width="5em",
                value=BackendVarState.limit,
                on_change=BackendVarState.set_limit,
            ),
            rx.button("Generate More", on_click=BackendVarState.generate_more),
        ),
        rx.chakra.list(
            rx.foreach(
                BackendVarState.page,
                lambda x, ix: rx.text(f"_backend[{ix + BackendVarState.offset}] = {x}"),
            ),
        ),
    )
```
