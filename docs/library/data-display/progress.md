---
components:
    - rx.progress

Progress: |
    lambda **props: rx.progress(value=50, **props)
---

# Progress

Progress is used to display the progress status for a task that takes a long time or consists of several steps.

```python exec
import reflex as rx
```
## Basic Example

`rx.progress` expects the `value` prop to set the progress value.
`width` is default to 100%, the width of its parent component.

```python demo
rx.vstack(
    rx.progress(value=0),
    rx.progress(value=50),
    rx.progress(value=100),
    width="50%",
)
```

For a dynamic progress, you can assign a state variable to the `value` prop instead of a constant value.

```python demo exec
import asyncio

class ProgressState(rx.State):
    value: int = 0

    @rx.event(background=True)
    async def start_progress(self):
        async with self:
            self.value = 0
        while self.value < 100:
            await asyncio.sleep(0.1)
            async with self:
                self.value += 1


def live_progress():
    return rx.hstack(
        rx.progress(value=ProgressState.value), 
        rx.button("Start", on_click=ProgressState.start_progress),
        width="50%"
    )
```
