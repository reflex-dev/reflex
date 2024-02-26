```python exec
import reflex as rx
from pcweb import constants, styles
```

# Background Tasks

A background task is a special type of `EventHandler` that may run
concurrently with other `EventHandler` functions. This enables long-running
tasks to execute without blocking UI interactivity.

A background task is defined by decorating an async `State` method with
`@rx.background`.

Whenever a background task needs to interact with the state, **it must enter an
`async with self` context block** which refreshes the state and takes an
exclusive lock to prevent other tasks or event handlers from modifying it
concurrently.  Because other `EventHandler` functions may modify state while the
task is running, **outside of the context block, Vars accessed by the background
task may be _stale_**. Attempting to modify the state from a background task
outside of the context block will raise an `ImmutableStateError` exception.

In the following example, the `my_task` event handler is decorated with
`@rx.background` and increments the `counter` variable every half second, as
long as certain conditions are met. While it is running, the UI remains
interactive and continues to process events normally.

```python demo exec
import asyncio
import reflex as rx


class MyTaskState(rx.State):
    counter: int = 0
    max_counter: int = 10
    running: bool = False
    _n_tasks: int = 0

    @rx.background
    async def my_task(self):
        async with self:
            # The latest state values are always available inside the context
            if self._n_tasks > 0:
                # only allow 1 concurrent task
                return
            
            # State mutation is only allowed inside context block
            self._n_tasks += 1

        while True:
            async with self:
                # Check for stopping conditions inside context
                if self.counter >= self.max_counter:
                    self.running = False
                if not self.running:
                    self._n_tasks -= 1
                    return

                self.counter += 1

            # Await long operations outside the context to avoid blocking UI
            await asyncio.sleep(0.5)

    def toggle_running(self):
        self.running = not self.running
        if self.running:
            return MyTaskState.my_task

    def clear_counter(self):
        self.counter = 0


def background_task_example():
    return rx.hstack(
        rx.heading(MyTaskState.counter, " /"),
        rx.chakra.number_input(
            value=MyTaskState.max_counter,
            on_change=MyTaskState.set_max_counter,
            width="8em",
        ),
        rx.button(
            rx.cond(~MyTaskState.running, "Start", "Stop"),
            on_click=MyTaskState.toggle_running,
        ),
        rx.button(
            "Reset",
            on_click=MyTaskState.clear_counter,
        ),
    )
```

## Task Lifecycle

When a background task is triggered, it starts immediately, saving a reference to
the task in `app.background_tasks`. When the task completes, it is removed from
the set.

Multiple instances of the same background task may run concurrently, and the
framework makes no attempt to avoid duplicate tasks from starting.

It is up to the developer to ensure that duplicate tasks are not created under
the circumstances that are undesirable. In the example above, the `_n_tasks`
backend var is used to control whether `my_task` will enter the increment loop,
or exit early.

## Background Task Limitations

Background tasks mostly work like normal `EventHandler` methods, with certain exceptions:

* Background tasks must be `async` functions.
* Background tasks cannot modify the state outside of an `async with self` context block.
* Background tasks may read the state outside of an `async with self` context block, but the value may be stale.
* Background tasks may not be directly called from other event handlers or background tasks. Instead use `yield` or `return` to trigger the background task.

## Low-level API

The `@rx.background` decorator is a convenience wrapper around the lower-level
`App.modify_state` async contextmanager. If more control over task lifecycle is
needed, arbitrary async tasks may safely manipulate the state using an
`async with app.modify_state(token) as state` context block. In this case the
`token` for a state is retrieved from `state.get_token()` and identifies a
single instance of the state (i.e. the state for an individual browser tab).

Care must be taken to **never directly modify the state outside of the
`modify_state` contextmanager**. If the code that creates the task passes a
direct reference to the state instance, this can introduce subtle bugs or not
work at all (if redis is used for state storage).

The following example creates an arbitrary `asyncio.Task` to fetch data and then
uses the low-level API to safely update the state and send the changes to the
frontend.

```python demo exec
import asyncio
import httpx
import reflex as rx

my_tasks = set()


async def _fetch_data(app, token):
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.github.com/zen")
    async with app.modify_state(token) as state:
        substate = state.get_substate(
            LowLevelState.get_full_name().split("."),
        )
        substate.result = response.text


class LowLevelState(rx.State):
    result: str = ""

    def fetch_data(self):
        task = asyncio.create_task(
            _fetch_data(
                app=rx.utils.prerequisites.get_app().app,
                token=self.get_token(),
            ),
        )

        # Always save a reference to your tasks until they are done
        my_tasks.add(task)
        task.add_done_callback(my_tasks.discard)


def low_level_example():
    return rx.vstack(
        rx.text(LowLevelState.result),
        rx.button(
            "Fetch Data",
            on_click=LowLevelState.fetch_data,
        ),
    )
```
