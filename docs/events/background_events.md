```python exec
import reflex as rx
from pcweb import constants, styles
```

# Background Tasks

A background task is a special type of `EventHandler` that may run
concurrently with other `EventHandler` functions. This enables long-running
tasks to execute without blocking UI interactivity.

A background task is defined by decorating an async `State` method with
`@rx.event(background=True)`.

```md alert warning
# `@rx.event(background=True)` used to be called `@rx.background`.
In Reflex version 0.6.5 and later, the `@rx.background` decorator has been renamed to `@rx.event(background=True)`.
```

Whenever a background task needs to interact with the state, **it must enter an
`async with self` context block** which refreshes the state and takes an
exclusive lock to prevent other tasks or event handlers from modifying it
concurrently. Because other `EventHandler` functions may modify state while the
task is running, **outside of the context block, Vars accessed by the background
task may be _stale_**. Attempting to modify the state from a background task
outside of the context block will raise an `ImmutableStateError` exception.

In the following example, the `my_task` event handler is decorated with
`@rx.event(background=True)` and increments the `counter` variable every half second, as
long as certain conditions are met. While it is running, the UI remains
interactive and continues to process events normally.

```md alert info
# Background events are similar to simple Task Queues like [Celery](https://www.fullstackpython.com/celery.html) allowing asynchronous events.
```

```python demo exec id=background_demo
import asyncio
import reflex as rx


class MyTaskState(rx.State):
    counter: int = 0
    max_counter: int = 10
    running: bool = False
    _n_tasks: int = 0

    @rx.event
    def set_max_counter(self, value: str):
        self.max_counter = int(value)

    @rx.event(background=True)
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

    @rx.event
    def toggle_running(self):
        self.running = not self.running
        if self.running:
            return MyTaskState.my_task

    @rx.event
    def clear_counter(self):
        self.counter = 0


def background_task_example():
    return rx.hstack(
        rx.heading(MyTaskState.counter, " /"),
        rx.input(
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

## Terminating Background Tasks on Page Close or Navigation

Sometimes, background tasks may continue running even after the user navigates away from the page or closes the browser tab. To handle such cases, you can check if the websocket associated with the state is disconnected and terminate the background task when necessary.

The solution involves checking if the client_token is still valid in the app.event_namespace.token_to_sid mapping. If the session is lost (e.g., the user navigates away or closes the page), the background task will stop.

```python
import asyncio
import reflex as rx

class State(rx.State):
    @rx.event(background=True)
    async def loop_function(self):
        while True:
            if self.router.session.client_token not in app.event_namespace.token_to_sid:
                print("WebSocket connection closed or user navigated away. Stopping background task.")
                break 
            
            print("Running background task...")
            await asyncio.sleep(2)  


@rx.page(on_load=State.loop_function)
def index():
    return rx.text("Hello, this page will manage background tasks and stop them when the page is closed or navigated away.")

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

- Background tasks must be `async` functions.
- Background tasks cannot modify the state outside of an `async with self` context block.
- Background tasks may read the state outside of an `async with self` context block, but the value may be stale.
- Background tasks may not be directly called from other event handlers or background tasks. Instead use `yield` or `return` to trigger the background task.
