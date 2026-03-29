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
        rx.heading(f"Number of times tooltip opened or closed: {TooltipState.num_opens}"),
        rx.heading(f"Tooltip open: {TooltipState.opened}"),
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
