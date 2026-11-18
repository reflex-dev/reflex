---
title: Autocomplete
---

# Autocomplete component

`rxe.mantine.autocomplete` is a component for providing suggestions as the user types. It is useful for enhancing user experience by offering relevant options based on input.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe


def autocomplete_example():
    return rx.vstack(
        rxe.mantine.autocomplete(
            data=["Apple", "Banana", "Cherry", "Date", "Elderberry"],
            placeholder="Type a fruit",
            label="Fruit Autocomplete",
            description="Select a fruit from the list",
        ),
    )
```

```python test
def test_autocomplete_suggests_fruits(demo, page):
    box = demo.get_by_role("textbox", name="Fruit Autocomplete")
    expect(demo.get_by_text("Select a fruit from the list")).to_be_visible()
    box.fill("an")
    expect(page.get_by_role("option")).to_have_text(["Banana"])
    page.get_by_role("option", name="Banana").click()
    expect(box).to_have_value("Banana")
```
