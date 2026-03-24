---
title: Ring Progress
---

# Ring Progress component

`rxe.mantine.ring_progress` is a component for displaying progress in a circular format. It is useful for visualizing completion percentages or other metrics in a compact and visually appealing way.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import random

class RingProgressState(rx.State):
    value: int = 50

    @rx.event
    def random(self):
        self.value = random.randint(0, 100)

def ring_progress_example():
    return rx.vstack(
        rxe.mantine.ring_progress(
            size=100,
            sections=[
                {"value": RingProgressState.value, "color": "blue"},
            ],
        ),
        rx.button("Randomize", on_click=RingProgressState.random),
    )
```
