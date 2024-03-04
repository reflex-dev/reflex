---
components:
    - rx.radix.popover.root
    - rx.radix.popover.content
    - rx.radix.popover.trigger
    - rx.radix.popover.close

only_low_level:
    - True

PopoverRoot: |
    lambda **props: rx.radix.themes.popover.root(
        rx.radix.themes.popover.trigger(
            rx.radix.themes.button("Popover"),
        ),
        rx.radix.themes.popover.content(
            rx.radix.themes.flex(
                rx.radix.themes.text("Simple Example"),
                rx.radix.themes.popover.close(
                    rx.radix.themes.button("Close"),
                ),
                direction="column",
                spacing="3",
            ),
        ),
        **props
    )

PopoverContent: |
    lambda **props: rx.radix.themes.popover.root(
        rx.radix.themes.popover.trigger(
            rx.radix.themes.button("Popover"),
        ),
        rx.radix.themes.popover.content(
            rx.radix.themes.flex(
                rx.radix.themes.text("Simple Example"),
                rx.radix.themes.popover.close(
                    rx.radix.themes.button("Close"),
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
            background="url('https://source.unsplash.com/random/800x600') center/cover",
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
