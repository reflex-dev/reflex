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

```python test
def test_css_and_radix_colors(demo):
    css = demo.get_by_text("CSS color")
    expect(css).to_have_css("background-color", "rgb(255, 0, 0)")
    expect(css).to_have_css("margin", "4px")
    radix = demo.get_by_text("Radix Color")
    expect(radix).to_have_css("background-color", "rgb(254, 235, 231)")
    expect(radix).to_have_css("margin", "12px")
    expect(radix).to_have_css("border-radius", "5px")
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

```python test
def test_stack_directions(demo):
    examples = demo.get_by_text("Example", exact=True)
    expect(examples).to_have_count(4)
    expect(examples.nth(0).locator("..")).to_have_css("flex-direction", "row")
    expect(examples.nth(2).locator("..")).to_have_css("flex-direction", "column")
    expect(examples.nth(0)).to_have_css("background-color", "rgb(255, 165, 0)")
    expect(examples.nth(1)).to_have_css("background-color", "rgb(173, 216, 230)")
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

```python test
def test_flex_cards_in_a_row(demo):
    cards = demo.get_by_text(re.compile(r"^Card \d$"))
    expect(cards).to_have_text(["Card 1", "Card 2", "Card 3"])
    expect(cards.first.locator("..")).to_have_css("display", "flex")
    tops = {round(cards.nth(i).bounding_box()["y"]) for i in range(3)}
    assert len(tops) == 1
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

```python test
def test_grid_three_columns(demo):
    cards = demo.get_by_text(re.compile(r"^Card \d+$"))
    expect(cards).to_have_text([f"Card {i}" for i in range(1, 13)])
    expect(cards.first.locator("..")).to_have_css(
        "grid-template-columns",
        re.compile(r"^\d+(\.\d+)?px \d+(\.\d+)?px \d+(\.\d+)?px$"),
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

```python test
def test_container_max_widths(demo):
    for width in ["448px", "688px", "880px"]:
        card = demo.get_by_text(
            f"This content is constrained to a max width of {width}."
        )
        expect(card.locator("..")).to_have_css("max-width", width)
```
