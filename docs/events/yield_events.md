```python exec
import reflex as rx

```

# Yielding Updates

A regular event handler will send a `StateUpdate` when it has finished running. This works fine for basic event, but sometimes we need more complex logic. To update the UI multiple times in an event handler, we can `yield` when we want to send an update.

To do so, we can use the Python keyword `yield`. For every yield inside the function, a `StateUpdate` will be sent to the frontend with the changes up to this point in the execution of the event handler.

This example below shows how to yield 100 updates to the UI.

```python demo exec

class MultiUpdateState(rx.State):
    count: int = 0

    @rx.event
    def timed_update(self):
        for i in range(100):
            self.count += 1
            yield


def multi_update():
    return rx.vstack(
    rx.text(MultiUpdateState.count),
    rx.button("Start", on_click=MultiUpdateState.timed_update)
)

```

Here is another example of yielding multiple updates with a loading icon.

```python demo exec

import asyncio

class ProgressExampleState(rx.State):
    count: int = 0
    show_progress: bool = False

    @rx.event
    async def increment(self):
        self.show_progress = True
        yield
        # Think really hard.
        await asyncio.sleep(0.5)
        self.count += 1
        self.show_progress = False

def progress_example():
    return rx.button(
        ProgressExampleState.count,
        on_click=ProgressExampleState.increment,
        loading=ProgressExampleState.show_progress,
    )

```

```md video https://youtube.com/embed/ITOZkzjtjUA?start=6463&end=6835
# Video: Asyncio with Yield
```

## Yielding Other Events

Events can also yield other events. This is useful when you want to chain events together. To do this, you can yield the event handler function itself.

```md alert
# Reference other Event Handler via class

When chaining another event handler with `yield`, access it via the state class, not `self`.
```

```python demo exec

import asyncio

class YieldEventsState(rx.State):
    count: int = 0
    show_progress: bool = False

    @rx.event
    async def add_five(self):
        self.show_progress = True
        yield
        # Think really hard.
        await asyncio.sleep(1)
        self.count += 5
        self.show_progress = False

    @rx.event
    async def increment(self):
        yield YieldEventsState.add_five
        yield YieldEventsState.add_five
        yield YieldEventsState.add_five


def multiple_yield_example():
    return rx.button(
        YieldEventsState.count,
        on_click=YieldEventsState.increment,
        loading=YieldEventsState.show_progress,
    )

```
