---
title: Timeline
---

# Timeline component
`rxe.mantine.timeline` is a component for displaying a sequence of events or milestones in a linear format. It is useful for visualizing progress, history, or any sequential information.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def timeline_example():
    return rx.vstack(
        rxe.mantine.timeline(
            rxe.mantine.timeline.item(
                title="Step 1",
                bullet="•",
            ),
            rxe.mantine.timeline.item(
                title="Step 2",
                bullet="•",
            ),
            rxe.mantine.timeline.item(
                title="Step 3",
                bullet="•",
            ),
            active=1,
            bullet_size=24,
            line_width=2,
            color="blue",
            
        )
    )
```
