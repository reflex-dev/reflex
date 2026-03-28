---
components:
  - rx.popover.root
  - rx.popover.content
  - rx.popover.trigger
  - rx.popover.close

only_low_level:
  - True

PopoverRoot: |
  lambda **props: rx.popover.root(
      rx.popover.trigger(
          rx.button("Popover"),
      ),
      rx.popover.content(
          rx.flex(
              rx.text("Simple Example"),
              rx.popover.close(
                  rx.button("Close"),
              ),
              direction="column",
              spacing="3",
          ),
      ),
      **props
  )

PopoverContent: |
  lambda **props: rx.popover.root(
      rx.popover.trigger(
          rx.button("Popover"),
      ),
      rx.popover.content(
          rx.flex(
              rx.text("Simple Example"),
              rx.popover.close(
                  rx.button("Close"),
              ),
              direction="column",
              spacing="3",
          ),
          **props
      ),
  )
---

```python exec
import reflex as rx
```

# Popover

A popover displays content, triggered by a button.

The `popover.root` contains all the parts of a popover.

The `popover.trigger` contains the button that toggles the popover.

The `popover.content` is the component that pops out when the popover is open.

The `popover.close` is the button that closes an open popover.

## Basic Example

```python demo
rx.popover.root(
    rx.popover.trigger(
        rx.button("Popover"),
    ),
    rx.popover.content(
        rx.flex(
            rx.text("Simple Example"),
            rx.popover.close(
                rx.button("Close"),
            ),
            direction="column",
            spacing="3",
        ),
    ),
)
```

## Examples in Context

```python demo

rx.popover.root(
    rx.popover.trigger(
        rx.button("Comment", variant="soft"),
    ),
    rx.popover.content(
        rx.flex(
            rx.avatar(
                "2",
                fallback="RX",
                radius="full"
            ),
            rx.box(
                rx.text_area(placeholder="Write a comment…", style={"height": 80}),
                rx.flex(
                    rx.checkbox("Send to group"),
                    rx.popover.close(
                        rx.button("Comment", size="1")
                    ),
                    spacing="3",
                    margin_top="12px",
                    justify="between",
                ),
                flex_grow="1",
            ),
            spacing="3"
        ),
        style={"width": 360},
    )
)
```

```python demo
rx.popover.root(
    rx.popover.trigger(
        rx.button("Feedback", variant="classic"),
    ),
    rx.popover.content(
        rx.inset(
            side="top",
            background="url('https://images.unsplash.com/5/unsplash-kitsune-4.jpg') center/cover",
            height="100px",
        ),
        rx.box(
            rx.text_area(placeholder="Write a comment…", style={"height": 80}),
            rx.flex(
                rx.checkbox("Send to group"),
                rx.popover.close(
                    rx.button("Comment", size="1")
                ),
                spacing="3",
                margin_top="12px",
                justify="between",
            ),
            padding_top="12px",
        ),
        style={"width": 360},
    )
)
```

## Popover with dynamic title

Code like below will not work as expected and it is necessary to place the dynamic title (`Index2State.language`) inside of an `rx.text` component.

```python
class Index2State(rx.State):
    language: str = "EN"

def index() -> rx.Component:
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(Index2State.language),
        ),
        rx.popover.content(
            rx.text('Success')
        )
    )
```

This code will work:

```python demo exec
class Index2State(rx.State):
    language: str = "EN"

def index() -> rx.Component:
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.text(Index2State.language)
            ),
        ),
        rx.popover.content(
            rx.text('Success')
        )
    )
```

## Events when the Popover opens or closes

The `on_open_change` event is called when the `open` state of the popover changes. It is used in conjunction with the `open` prop, which is passed to the event handler.

```python demo exec
class PopoverState(rx.State):
    num_opens: int = 0
    opened: bool = False

    @rx.event
    def count_opens(self, value: bool):
        self.opened = value
        self.num_opens += 1


def popover_example():
    return rx.flex(
        rx.heading(f"Number of times popover opened or closed: {PopoverState.num_opens}"),
        rx.heading(f"Popover open: {PopoverState.opened}"),
        rx.popover.root(
            rx.popover.trigger(
                rx.button("Popover"),
            ),
            rx.popover.content(
                rx.flex(
                    rx.text("Simple Example"),
                    rx.popover.close(
                        rx.button("Close"),
                    ),
                    direction="column",
                    spacing="3",
                ),
            ),
            on_open_change=PopoverState.count_opens,
        ),
        direction="column",
        spacing="3",
    )
```
