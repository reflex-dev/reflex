---
title: MultiSelect
---

# MultiSelect component

`rxe.mantine.multi_select` is a component for selecting multiple options from a list. It allows users to choose one or more items, making it suitable for scenarios where multiple selections are required.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe


class MultiSelectState(rx.State):
    selected_fruits: list = []

    def set_selected_fruits(self, value: list):
        self.selected_fruits = value


def multi_select_example():
    return rx.vstack(
        rxe.mantine.multi_select(
            label="Select fruits",
            placeholder="Pick all that you like",
            data=["Apple", "Banana", "Cherry", "Date", "Elderberry"],
            value=MultiSelectState.selected_fruits,
            on_change=MultiSelectState.set_selected_fruits,
        )
    )
```

```python test
def test_pick_several_fruits(demo, page):
    demo.get_by_role("textbox", name="Select fruits").click()
    page.get_by_role("option", name="Banana").click()
    page.get_by_role("option", name="Date").click()
    expect(demo.locator(".mantine-Pill-label")).to_have_text(["Banana", "Date"])
```
