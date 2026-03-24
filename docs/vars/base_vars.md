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
    return rx.center(
          rx.vstack(
                rx.heading(TickerState.ticker, size="3"),
                rx.text(f"Current Price: {TickerState.price}", font_size="md"),
                rx.text("Change: 4%", color="green"),
            ),

    )
```

In this example `ticker` and `price` are base vars in the app, which can be modified at runtime.

```md alert warning
# Vars must be JSON serializable.

Vars are used to communicate between the frontend and backend. They must be primitive Python types, Plotly figures, Pandas dataframes, or [a custom defined type]({vars.custom_vars.path}).
```

## Accessing state variables on different pages

State is just a python class and so can be defined on one page and then imported and used on another. Below we define `TickerState` class on the page `state.py` and then import it and use it on the page `index.py`.

```python
# state.py

class TickerState(rx.State):
    ticker: str = "AAPL"
    price: str = "$150"
```

```python
# index.py
from .state import TickerState

def ticker_example():
    return rx.center(
          rx.vstack(
                rx.heading(TickerState.ticker, size="3"),
                rx.text(f"Current Price: \{TickerState.price}", font_size="md"),
                rx.text("Change: 4%", color="green"),
            ),

    )
```

## Backend-only Vars

Any Var in a state class that starts with an underscore (`_`) is considered backend
only and will **not be synchronized with the frontend**. Data associated with a
specific session that is _not directly rendered on the frontend should be stored
in a backend-only var_ to reduce network traffic and improve performance.

They have the advantage that they don't need to be JSON serializable, however
they must still be pickle-able to be used with redis in prod mode. They are
not directly renderable on the frontend, and **may be used to store sensitive
values that should not be sent to the client**.

```md alert warning
# Protect auth data and sensitive state in backend-only vars.

Regular vars and computed vars should **only** be used for rendering the state
of your app in the frontend. Having any type of permissions or authenticated state based on
a regular var presents a security risk as you may assume these have shared control
with the frontend (client) due to default setter methods.

For improved security, `state_auto_setters=False` may be set in `rxconfig.py`
to prevent the automatic generation of setters for regular vars, however, the
client will still be able to locally modify the contents of frontend vars as
they are presented in the UI.
```

For example, a backend-only var is used to store a large data structure which is
then paged to the frontend using cached vars.

```python demo exec
import numpy as np


class BackendVarState(rx.State):
    _backend: np.ndarray = np.array([random.randint(0, 100) for _ in range(100)])
    offset: int = 0
    limit: int = 10

    @rx.var(cache=True)
    def page(self) -> list[int]:
        return [
            int(x)  # explicit cast to int
            for x in self._backend[self.offset : self.offset + self.limit]
        ]

    @rx.var(cache=True)
    def page_number(self) -> int:
        return (self.offset // self.limit) + 1 + (1 if self.offset % self.limit else 0)

    @rx.var(cache=True)
    def total_pages(self) -> int:
        return len(self._backend) // self.limit + (1 if len(self._backend) % self.limit else 0)

    @rx.event
    def prev_page(self):
        self.offset = max(self.offset - self.limit, 0)

    @rx.event
    def next_page(self):
        if self.offset + self.limit < len(self._backend):
            self.offset += self.limit

    @rx.event
    def generate_more(self):
        self._backend = np.append(self._backend, [random.randint(0, 100) for _ in range(random.randint(0, 100))])

    @rx.event
    def set_limit(self, value: str):
        self.limit = int(value)

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
            rx.input(
                width="5em",
                value=BackendVarState.limit,
                on_change=BackendVarState.set_limit,
            ),
            rx.button("Generate More", on_click=BackendVarState.generate_more),
        ),
        rx.list(
            rx.foreach(
                BackendVarState.page,
                lambda x, ix: rx.text(f"_backend[{ix + BackendVarState.offset}] = {x}"),
            ),
        ),
    )
```


## Using rx.field / rx.Field to improve type hinting for vars

When defining state variables you can use `rx.Field[T]` to annotate the variable's type. Then, you can initialize the variable using `rx.field(default_value)`, where `default_value` is an instance of type `T`. 

This approach makes the variable's type explicit, aiding static analysis tools in type checking. In addition, it shows you what methods are allowed to modify the variable in your frontend code, as they are listed in the type hint.

Below are two examples:

```python
import reflex as rx

app = rx.App()


class State(rx.State):
    x: rx.Field[bool] = rx.field(False)

    def flip(self):
        self.x = not self.x


@app.add_page
def index():
    return rx.vstack(
        rx.button("Click me", on_click=State.flip),
        rx.text(State.x),
        rx.text(~State.x),
    )
```

Here `State.x`, as it is typed correctly as a `boolean` var, gets better code completion, i.e. here we get options such as `to_string()` or `equals()`.


```python
import reflex as rx

app = rx.App()


class State(rx.State):
    x: rx.Field[dict[str, list[int]]] = rx.field(default_factory=dict)


@app.add_page
def index():
    return rx.vstack(
        rx.text(State.x.values()[0][0]),
    )
```

Here `State.x`, as it is typed correctly as a `dict` of `str` to `list` of `int` var, gets better code completion, i.e. here we get options such as `contains()`, `keys()`, `values()`, `items()` or `merge()`.