---
components:
    - rx.stack
    - rx.hstack
    - rx.vstack
Stack: |
    lambda **props: rx.stack(
        rx.card("Card 1", size="2"), rx.card("Card 2", size="2"), rx.card("Card 3", size="2"),
        width="100%",
        height="20vh",
        **props,
    )
---

```python exec
import reflex as rx
```

# Stack

`Stack` is a layout component used to group elements together and apply a space between them.

`vstack` is used to stack elements in the vertical direction.

`hstack` is used to stack elements in the horizontal direction.

`stack` is used to stack elements in the vertical or horizontal direction.

These components are based on the `flex` component and therefore inherit all of its props.

The `stack` component can be used with the `flex_direction` prop to set to either `row` or `column` to set the direction.

```python demo
rx.flex(
    rx.stack(
        rx.box(
            "Example",
            bg="orange",
            border_radius="3px",
            width="20%",
        ),
        rx.box(
            "Example",
            bg="lightblue",
            border_radius="3px",
            width="30%",
        ),
        rx.box(
            "Example",
            bg="lightgreen",
            border_radius="3px",
            width="50%",
        ),
        flex_direction="row",
        width="100%",
    ),
    rx.stack(
        rx.box(
            "Example",
            bg="orange",
            border_radius="3px",
            width="20%",
        ),
        rx.box(
            "Example",
            bg="lightblue",
            border_radius="3px",
            width="30%",
        ),
        rx.box(
            "Example",
            bg="lightgreen",
            border_radius="3px",
            width="50%",
        ),
        flex_direction="column",
        width="100%",
    ),
    width="100%",
)
```

## Hstack

```python demo
rx.hstack(
    rx.box(
        "Example", bg="red", border_radius="3px", width="10%"
    ),
    rx.box(
        "Example",
        bg="orange",
        border_radius="3px",
        width="10%",
    ),
    rx.box(
        "Example",
        bg="yellow",
        border_radius="3px",
        width="10%",
    ),
    rx.box(
        "Example",
        bg="lightblue",
        border_radius="3px",
        width="10%",
    ),
    rx.box(
        "Example",
        bg="lightgreen",
        border_radius="3px",
        width="60%",
    ),
    width="100%",
)
```

## Vstack

```python demo
rx.vstack(
    rx.box(
        "Example", bg="red", border_radius="3px", width="20%"
    ),
    rx.box(
        "Example",
        bg="orange",
        border_radius="3px",
        width="40%",
    ),
    rx.box(
        "Example",
        bg="yellow",
        border_radius="3px",
        width="60%",
    ),
    rx.box(
        "Example",
        bg="lightblue",
        border_radius="3px",
        width="80%",
    ),
    rx.box(
        "Example",
        bg="lightgreen",
        border_radius="3px",
        width="100%",
    ),
    width="100%",
)
```

## Real World Example

```python demo
rx.hstack(
    rx.box(
        rx.heading("Saving Money"),
        rx.text("Saving money is an art that combines discipline, strategic planning, and the wisdom to foresee future needs and emergencies. It begins with the simple act of setting aside a portion of one's income, creating a buffer that can grow over time through interest or investments.", margin_top="0.5em"),
        padding="1em",
        border_width="1px",
    ),
    rx.box(
        rx.heading("Spending Money"),
        rx.text("Spending money is a balancing act between fulfilling immediate desires and maintaining long-term financial health. It's about making choices, sometimes indulging in the pleasures of the moment, and at other times, prioritizing essential expenses.", margin_top="0.5em"),
        padding="1em",
        border_width="1px",
    ),
    gap="2em",
)

```
