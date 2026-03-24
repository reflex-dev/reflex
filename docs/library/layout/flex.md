---
components:
  - rx.flex
---

```python exec
import reflex as rx
```

# Flex

The Flex component is used to make [flexbox layouts](https://developer.mozilla.org/en-US/docs/Learn/CSS/CSS_layout/Flexbox).
It makes it simple to arrange  child components in horizontal or vertical directions, apply wrapping,
justify and align  content, and automatically size components based on available space, making it
ideal for building responsive layouts.

By default, children are arranged horizontally (`direction="row"`) without wrapping.

## Basic Example

```python demo
rx.flex(
    rx.card("Card 1"),
    rx.card("Card 2"),
    rx.card("Card 3"),
    rx.card("Card 4"),
    rx.card("Card 5"),
    spacing="2",
    width="100%",
)
```

## Wrapping

With `flex_wrap="wrap"`, the children will wrap to the next line instead of being resized.

```python demo
rx.flex(
    rx.foreach(
        rx.Var.range(10),
        lambda i: rx.card(f"Card {i + 1}", width="16%"),
    ),
    spacing="2",
    flex_wrap="wrap",
    width="100%",
)
```

## Direction

With `direction="column"`, the children will be arranged vertically.

```python demo
rx.flex(
    rx.card("Card 1"),
    rx.card("Card 2"),
    rx.card("Card 3"),
    rx.card("Card 4"),
    spacing="2",
    direction="column",
)
```

## Alignment

Two props control how children are aligned within the Flex component:

* `align` controls how children are aligned along the cross axis (vertical for `row` and horizontal for `column`).
* `justify` controls how children are aligned along the main axis (horizontal for `row` and vertical for `column`).

The following example visually demonstrates the effect of these props with different `wrap` and `direction` values.

```python demo exec
class FlexPlaygroundState(rx.State):
    align: str = "stretch"
    justify: str = "start"
    direction: str = "row"
    wrap: str = "nowrap"

    @rx.event
    def set_align(self, value: str):
        self.align = value

    @rx.event
    def set_justify(self, value: str):
        self.justify = value

    @rx.event
    def set_direction(self, value: str):
        self.direction = value

    @rx.event
    def set_wrap(self, value: str):
        self.wrap = value


def select(label, items, value, on_change):
    return rx.flex(
        rx.text(label),
        rx.select.root(
            rx.select.trigger(),
            rx.select.content(
                *[
                    rx.select.item(item, value=item)
                    for item in items
                ]
            ),
            value=value,
            on_change=on_change,
        ),
        align="center",
        justify="center",
        direction="column",
    )


def selectors():
    return rx.flex(
        select("Wrap", ["nowrap", "wrap", "wrap-reverse"], FlexPlaygroundState.wrap, FlexPlaygroundState.set_wrap),
        select("Direction", ["row", "column", "row-reverse", "column-reverse"], FlexPlaygroundState.direction, FlexPlaygroundState.set_direction),
        select("Align", ["start", "center", "end", "baseline", "stretch"], FlexPlaygroundState.align, FlexPlaygroundState.set_align),
        select("Justify", ["start", "center", "end", "between"], FlexPlaygroundState.justify, FlexPlaygroundState.set_justify),
        width="100%",
        spacing="2",
        justify="between",
    )


def example1():
    return rx.box(
        selectors(),
        rx.flex(
            rx.foreach(
                rx.Var.range(10),
                lambda i: rx.card(f"Card {i + 1}", width="16%"),
            ),
            spacing="2",
            direction=FlexPlaygroundState.direction,
            align=FlexPlaygroundState.align,
            justify=FlexPlaygroundState.justify,
            wrap=FlexPlaygroundState.wrap,
            width="100%",
            height="20vh",
            margin_top="16px",
        ),
        width="100%",
    )
```

## Size Hinting

When a child component is included in a flex container,
the `flex_grow` (default `"0"`) and `flex_shrink` (default `"1"`) props control
how the box is sized relative to other components in the same container.

The resizing always applies to the main axis of the flex container. If the direction is
`row`, then the sizing applies to the `width`. If the direction is `column`, then the sizing
applies to the `height`. To set the optimal size along the main axis, the `flex_basis` prop
is used and may be either a percentage or CSS size units. When unspecified, the
corresponding `width` or `height` value is used if set, otherwise the content size is used.

When `flex_grow="0"`, the box will not grow beyond the `flex_basis`.

When `flex_shrink="0"`, the box will not shrink to less than the `flex_basis`.

These props are used when creating flexible responsive layouts.

Move the slider below and see how adjusting the width of the flex container
affects the computed  sizes of the flex items based on the props that are set.

```python demo exec
class FlexGrowShrinkState(rx.State):
    width_pct: list[int] = [100]

    @rx.event
    def set_width_pct(self, value: list[int | float]):
        self.width_pct = [int(value[0])]


def border_box(*children, **props):
    return rx.box(
        *children,
        border="1px solid var(--gray-10)",
        border_radius="2px",
        **props,
    )


def example2():
    return rx.box(
        rx.flex(
            border_box("flex_shrink=0", flex_shrink="0", width="100px"),
            border_box("flex_shrink=1", flex_shrink="1", width="200px"),
            border_box("flex_grow=0", flex_grow="0"),
            border_box("flex_grow=1", flex_grow="1"),
            width=f"{FlexGrowShrinkState.width_pct}%",
            margin_bottom="16px",
            spacing="2",
        ),
        rx.slider(
            min=0,
            max=100,
            value=FlexGrowShrinkState.width_pct,
            on_change=FlexGrowShrinkState.set_width_pct,
        ),
        width="100%",
    )
```
