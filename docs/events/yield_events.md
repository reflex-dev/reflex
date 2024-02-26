```python exec
import reflex as rx

```

# Yielding Multiple Updates

A regular event handler will send a `StateUpdate` when it has finished running. This works fine for basic event, but sometimes we need more complex logic. To update the UI multiple times in an event handler, we can `yield` when we want to send an update.

To do so, we can use the Python keyword `yield`. For every yield inside the function, a `StateUpdate` will be sent to the frontend with the changes up to this point in the execution of the event handler.

```python demo exec

import asyncio

class MultiUpdateState(rx.State):
    count: int = 0

    async def timed_update(self):
        for i in range(5):
            await asyncio.sleep(0.5)
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

    async def increment(self):
        self.show_progress = True
        yield
        # Think really hard.
        await asyncio.sleep(0.5)
        self.count += 1
        self.show_progress = False

def progress_example():
    return rx.cond(
        ProgressExampleState.show_progress,
        rx.chakra.circular_progress(is_indeterminate=True),
        rx.heading(
            ProgressExampleState.count,
            on_click=ProgressExampleState.increment,
            _hover={"cursor": "pointer"},
        )
    )

```
