---
components:
    - rx.radix.hover_card.root
    - rx.radix.hover_card.content
    - rx.radix.hover_card.trigger

only_low_level:
    - True

HoverCardRoot: |
    lambda **props: rx.radix.themes.hover_card.root(
        rx.radix.themes.hover_card.trigger(
            rx.radix.themes.link("Hover over me"),
        ),
        rx.radix.themes.hover_card.content(
            rx.radix.themes.text("This is the tooltip content."),
        ),
        **props
    )

HoverCardContent: |
    lambda **props: rx.radix.themes.hover_card.root(
        rx.radix.themes.hover_card.trigger(
            rx.radix.themes.link("Hover over me"),
        ),
        rx.radix.themes.hover_card.content(
            rx.radix.themes.text("This is the tooltip content."),
            **props
        ),
    )
---

```python exec
import reflex as rx
```

# Hovercard

The `hover_card.root` contains all the parts of a hover card.

The `hover_card.trigger` wraps the link that will open the hover card.

The `hover_card.content` contains the content of the open hover card.

```python demo
rx.text(
    "Hover over the text to see the tooltip. ",
    rx.hover_card.root(
        rx.hover_card.trigger(
            rx.link("Hover over me", color_scheme="blue", underline="always"),
        ),
        rx.hover_card.content(
            rx.text("This is the tooltip content."),
        ),
    ),
)
```

```python demo
rx.text(
    "Hover over the text to see the tooltip. ",
    rx.hover_card.root(
        rx.hover_card.trigger(
            rx.link("Hover over me", color_scheme="blue", underline="always"),
        ),
        rx.hover_card.content(
            rx.grid(
                rx.inset(
                    side="left",
                    pr="current",
                    background="url('https://source.unsplash.com/random/800x600') center/cover",
                    height="full",
                ),
                rx.box(
                    rx.text_area(placeholder="Write a comment…", style={"height": 80}),
                    rx.flex(
                        rx.checkbox("Send to group"),
                        spacing="3",
                        margin_top="12px",
                        justify="between",
                    ),
                    padding_left="12px",
                ),
                columns="120px 1fr",
            ),
            style={"width": 360},
        ),
    ),
)
```

## Events when the Hovercard opens or closes

The `on_open_change` event is called when the `open` state of the hovercard changes. It is used in conjunction with the `open` prop, which is passed to the event handler.

```python demo exec
class HovercardState(rx.State):
    num_opens: int = 0
    opened: bool = False

    def count_opens(self, value: bool):
        self.opened = value
        self.num_opens += 1


def hovercard_example():
    return rx.flex(
        rx.heading(f"Number of times hovercard opened or closed: {HovercardState.num_opens}"),
        rx.heading(f"Hovercard open: {HovercardState.opened}"),
        rx.text(
            "Hover over the text to see the tooltip. ",
            rx.hover_card.root(
                rx.hover_card.trigger(
                    rx.link("Hover over me", color_scheme="blue", underline="always"),
                ),
                rx.hover_card.content(
                    rx.text("This is the tooltip content."),
                ),
                on_open_change=HovercardState.count_opens,
            ),
        ),
        direction="column",
        spacing="3",
    )
```
