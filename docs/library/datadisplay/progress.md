---
components:
    - rx.radix.primitives.progress.root

Progress: |
    lambda **props: rx.progress(value=50, width="100%", **props)
---

```python exec
import reflex as rx
import asyncio

class ProgressState(rx.State):
    value: int = 0

    @rx.background
    async def start_progress(self):
        async with self:
            self.value = 0
        while self.value < 100:
            await asyncio.sleep(0.1)
            async with self:
                self.value += 1
```

# Progress

Progress is used to display the progress status for a task that takes a long time or consists of several steps.

## Basic Example

`rx.progress` expect the `value` prop to set the progress value.

```python demo
rx.vstack(
    rx.progress(value=0, width="100%"),
    rx.progress(value=50, width="100%"),
    rx.progress(value=100, width="100%"),
    gap="1em",
    min_width=["10em", "20em"],
)
```

For a dynamic progress, you can assign a state variable to the `value` prop instead of a constant value.

```python demo
rx.hstack(
    rx.progress(value=ProgressState.value, width="100%"), 
    rx.button("Start", on_click=ProgressState.start_progress),
    width="10em"
)
```
