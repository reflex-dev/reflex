---
title: Semi Circle Progress
---

# Semi Circle Progress component
`rxe.mantine.semi_circle_progress` is a component for displaying progress in a semi-circular format. It is useful for visualizing completion percentages or other metrics in a compact and visually appealing way.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import random

class SemiCircleProgressState(rx.State):
    value: int = 50

    @rx.event
    def random(self):
        self.value = random.randint(0, 100)

def semi_circle_progress_example():
    return rx.vstack(
        rxe.mantine.semi_circle_progress(
            size=100,
            value=SemiCircleProgressState.value,
        ),
        rx.button("Randomize", on_click=SemiCircleProgressState.random),
    )
```
