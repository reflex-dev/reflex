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

```python test
def test_timeline_marks_first_two_steps_active(demo):
    items = demo.locator(".mantine-Timeline-item")
    expect(items.locator(".mantine-Timeline-itemTitle")).to_have_text([
        "Step 1",
        "Step 2",
        "Step 3",
    ])
    expect(items.nth(0)).to_have_attribute("data-active", "true")
    expect(items.nth(1)).to_have_attribute("data-active", "true")
    expect(items.nth(2)).not_to_have_attribute("data-active", "true")
```
