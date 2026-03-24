```python exec
import reflex as rx
```

# Layout Components

Layout components such as `rx.flex`, `rx.container`, `rx.box`, etc. are used to organize and structure the visual presentation of your application. This page gives a breakdown of when and how each of these components might be used.

```md video https://youtube.com/embed/ITOZkzjtjUA?start=3311&end=3853
# Video: Example of Laying Out the Main Content of a Page
```

## Box

`rx.box` is a generic component that can apply any CSS style to its children. It's a building block that can be used to apply a specific layout or style property.

**When to use:** Use `rx.box` when you need to apply specific styles or constraints to a part of your interface.


```python demo
rx.box(
    rx.box(
        "CSS color",
        background_color="red",
        border_radius="2px",
        width="50%",
        margin="4px",
        padding="4px",
    ),
    rx.box(
        "Radix Color",
        background_color=rx.color("tomato", 3),
        border_radius="5px",
        width="80%",
        margin="12px",
        padding="12px",
    ),
    text_align="center",
    width="100%",
)
```

## Stack

`rx.stack` is a layout component that arranges its children in a single column or row, depending on the direction. It’s useful for consistent spacing between elements.

**When to use:** Use `rx.stack` when you need to lay out a series of components either vertically or horizontally with equal spacing.

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
        flex_direction="column",
        width="100%",
    ),
    width="100%",
)
```

## Flex

The `rx.flex` component is used to create a flexible box layout, inspired by [CSS Flexbox](https://developer.mozilla.org/en-US/docs/Learn/CSS/CSS_layout/Flexbox). It's ideal for designing a layout where the size of the items can grow and shrink dynamically based on the available space.

**When to use:** Use `rx.flex` when you need a responsive layout that adjusts the size and position of child components dynamically.


```python demo
rx.flex(
    rx.card("Card 1"),
    rx.card("Card 2"),
    rx.card("Card 3"),
    spacing="2",
    width="100%",
)
```


## Grid

`rx.grid` components are used to create complex responsive layouts based on a grid system, similar to [CSS Grid Layout](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_grid_layout).

**When to use:** Use `rx.grid` when dealing with complex layouts that require rows and columns, especially when alignment and spacing among multiple axes are needed.

```python demo
rx.grid(
    rx.foreach(
        rx.Var.range(12),
        lambda i: rx.card(f"Card {i + 1}", height="10vh"),
    ),
    columns="3",
    spacing="4",
    width="100%",
)
```

## Container

The `rx.container` component typically provides padding and fixes the maximum width of the content inside it, often used to center content on large screens.

**When to use:** Use `rx.container` for wrapping your application’s content in a centered block with some padding.

```python demo
rx.box(
    rx.container(
        rx.card(
            "This content is constrained to a max width of 448px.",
            width="100%",
        ),
        size="1",
    ),
    rx.container(
        rx.card(
            "This content is constrained to a max width of 688px.",
            width="100%",
        ),
        size="2",
    ),
    rx.container(
        rx.card(
            "This content is constrained to a max width of 880px.",
            width="100%",
        ),
        size="3",
    ),
    background_color="var(--gray-3)",
    width="100%",
)
```