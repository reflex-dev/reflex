---
components:
  - rx.tooltip

Tooltip: |
  lambda **props: rx.tooltip(
      rx.button("Hover over me"),
      content="This is the tooltip content.",
      **props,
  )
---

```python exec
import reflex as rx
```

# Tooltip

A `tooltip` displays informative information when users hover over or focus on an element.

It takes a `content` prop, which is the content associated with the tooltip.

```python demo
rx.tooltip(
    rx.button("Hover over me"),
    content="This is the tooltip content.",
)
```

```python test
def test_tooltip_shows_on_hover(demo, page):
    demo.get_by_role("button", name="Hover over me").hover()
    expect(page.get_by_role("tooltip")).to_have_text("This is the tooltip content.")
    # Leave in steps: the tooltip keeps a hover grace area around its trigger.
    page.mouse.move(0, 0, steps=10)
    expect(page.get_by_role("tooltip")).to_have_count(0)
```

## Events when the Tooltip opens or closes

The `on_open_change` event is called when the `open` state of the tooltip changes. It is used in conjunction with the `open` prop, which is passed to the event handler.

```python demo exec
class TooltipState(rx.State):
    num_opens: int = 0
    opened: bool = False

    @rx.event
    def count_opens(self, value: bool):
        self.opened = value
        self.num_opens += 1


def index():
    return rx.flex(
        rx.heading(
            f"Number of times tooltip opened or closed: {TooltipState.num_opens}",
            as_="h2",
        ),
        rx.heading(f"Tooltip open: {TooltipState.opened}", as_="h2"),
        rx.text(
            "Hover over the button to see the tooltip.",
            rx.tooltip(
                rx.button("Hover over me"),
                content="This is the tooltip content.",
                on_open_change=TooltipState.count_opens,
            ),
        ),
        direction="column",
        spacing="3",
    )
```

```python test
def test_tooltip_on_open_change_counts(demo, page):
    headings = demo.get_by_role("heading")
    expect(headings).to_have_text([
        "Number of times tooltip opened or closed: 0",
        "Tooltip open: false",
    ])
    demo.get_by_role("button", name="Hover over me").hover()
    expect(page.get_by_role("tooltip")).to_have_text("This is the tooltip content.")
    expect(headings).to_have_text([
        "Number of times tooltip opened or closed: 1",
        "Tooltip open: true",
    ])
    page.mouse.move(0, 0, steps=10)
    expect(headings).to_have_text([
        "Number of times tooltip opened or closed: 2",
        "Tooltip open: false",
    ])
```
