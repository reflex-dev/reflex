```python exec
import random
import time

import reflex as rx
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
    ticker: str = "AAPL"
    price: str = "$150"


def ticker_example():
    return rx.center(
        rx.vstack(
            rx.heading(TickerState.ticker, as_="h2", size="3"),
            rx.text(f"Current Price: {TickerState.price}", font_size="md"),
            rx.text("Change: 4%", color="green"),
        ),
    )
```

In this example `ticker` and `price` are base vars in the app, which can be modified at runtime.

```md alert warning
# Vars must be JSON serializable.

Vars are used to communicate between the frontend and backend. They must be primitive Python types, Plotly figures, Pandas dataframes, or [a custom defined type](/docs/vars/custom-vars).
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
            rx.heading(TickerState.ticker, as_="h2", size="3"),
            rx.text(f"Current Price: {TickerState.price}", font_size="md"),
            rx.text("Change: 4%", color="green"),
        ),
    )
```

## Changing Defaults

A state var is a descriptor on its state class, so assigning to it through the
class raises `TypeError` instead of replacing the var. To change a var's default,
call `set_default` on the var's field with either a `default` value or a
`default_factory` function:

```python
import time


class WatchlistState(rx.State):
    ticker: str = "AAPL"
    symbols: list[str] = []
    opened_at: float = 0.0


WatchlistState.__fields__["ticker"].set_default(default="MSFT")
WatchlistState.__fields__["symbols"].set_default(default=["AAPL", "MSFT"])
WatchlistState.__fields__["opened_at"].set_default(default_factory=time.time)
```

The default applies to values not yet stored on an instance, which includes
every new session and `reset()`. Values already stored on an instance stay the
same. Pass exactly one of `default` and `default_factory`; a `default_factory`
is called for each new instance. `set_default` copies a mutable `default`, such
as a list, when you set it and gives each instance its own copy, so sessions
never share it and later changes to the value you passed do not reach the
default. It does not check the value against the var's annotation. A browser
storage var keeps its storage name and options only with a storage value as its
default, such as `rx.LocalStorage("dark", name="theme")`. Given a plain string,
a var annotated `str` becomes an ordinary var, and one annotated with a storage
type, such as `rx.LocalStorage`, stays in browser storage under the default key
and options.

An inherited var belongs to the state that declared it, so changing its field
also changes the default for every state that inherits it. Each generated
`ComponentState` class owns copies of its fields, allowing
[`get_component` to configure defaults](/docs/state-structure/component-state/#passing-props)
independently for each component.

In tests, patch the field rather than the class attribute, which raises the same
`TypeError`:

```python
from unittest import mock

with mock.patch.object(WatchlistState.__fields__["ticker"], "default", "MSFT"):
    ...
```

Declare class-level configuration, such as a client or a lock, as a `ClassVar`.
It stays an ordinary class attribute, so assigning it through the class is
allowed, and it is never copied for each instance. Each backend worker process
holds its own value, though, so a lock only serializes the sessions on its own
worker. A value set at import time, such as at module level, starts the same in
every worker, but a change made after the workers start, such as in an event
handler, never reaches the other workers. Keep a value that sessions must share
at runtime in an [`rx.SharedState`](/docs/state-structure/shared-state/) or an
external store.

```md alert warning
# Change defaults before the app starts running.

Changing a default on a mixin only affects states created afterwards. Do not
change defaults in event handlers, lifespan tasks, or at any other time after the
app has started running: such a change only affects the worker process that made
it.
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

Regular vars and computed vars are synchronized to the frontend so they can be
rendered in the UI. Any value placed in a regular var is serialized and sent to
the client, where it is visible to anyone who inspects the page or network
traffic.

For permissions, authentication tokens, or other sensitive state, store the
value in a backend-only var (prefixed with `_`) so it is never sent to the
client.
```

For example, a backend-only var is used to store a large data structure which is
then paged to the frontend using cached vars.

Read and write a backend var through a state instance, such as `self._token`.
Reading `MyState._token` through the class returns its field descriptor, whose
`default_value()` method returns the default (a fresh copy if it is mutable). Use
it to build the UI from a constant, such as
`rx.foreach(MyState._options.default_value(), rx.text)` for a backend var
`_options`. Assigning to `MyState._token` raises `TypeError`: change its default
through its field as described above.

For class-level configuration, declare a `ClassVar` instead:

```python
from typing import ClassVar


class MyState(rx.State):
    _endpoint: ClassVar[str] = "https://example.com/api"
    _token: str = ""


MyState._endpoint = "https://example.com/v2"
```

`ClassVar` values are ordinary class attributes and are not part of session state.
Reading one on the class returns the plain value, and an object that cannot be
copied, such as a client or lock, is shared rather than copied for each instance.
Each backend worker holds its own value, as described under
[Changing Defaults](#changing-defaults).

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
        return len(self._backend) // self.limit + (
            1 if len(self._backend) % self.limit else 0
        )

    @rx.event
    def prev_page(self):
        self.offset = max(self.offset - self.limit, 0)

    @rx.event
    def next_page(self):
        if self.offset + self.limit < len(self._backend):
            self.offset += self.limit

    @rx.event
    def generate_more(self):
        self._backend = np.append(
            self._backend,
            [random.randint(0, 100) for _ in range(random.randint(0, 100))],
        )

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
            rx.text(
                f"Page {BackendVarState.page_number} / {BackendVarState.total_pages}"
            ),
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
