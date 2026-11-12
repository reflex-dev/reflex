```python exec
import reflex as rx
```

# Multi-column and row layout

A simple responsive multi-column and row layout. We specify the number of columns/rows to the `flex_direction` property as a list. The layout will automatically adjust the number of columns/rows based on the screen size.

For details, see the [responsive docs page](/docs/styling/responsive/).

## Column

```python demo
rx.flex(
    rx.box(bg=rx.color("accent", 3), width="100%", height="100%"),
    rx.box(bg=rx.color("accent", 5), width="100%", height="100%"),
    rx.box(bg=rx.color("accent", 7), width="100%", height="100%"),
    bg=rx.color("accent", 10),
    spacing="4",
    padding="1em",
    flex_direction=["column", "column", "row"],
    height="600px",
    width="100%",
)
```

```python test
def test_three_equal_columns(demo):
    row = demo.locator("> .rt-Flex")
    expect(row).to_have_css("flex-direction", "row")
    expect(row).to_have_css("height", "600px")
    columns = row.locator("> div")
    expect(columns).to_have_count(3)
    for i in range(3):
        expect(columns.nth(i)).to_have_css("height", "568px")
```

```python demo
rx.flex(
    rx.box(bg=rx.color("accent", 3), width="100%", height="100%"),
    rx.box(
        bg=rx.color("accent", 5),
        width=["100%", "100%", "50%"],
        height=["50%", "50%", "100%"],
    ),
    rx.box(bg=rx.color("accent", 7), width="100%", height="100%"),
    rx.box(
        bg=rx.color("accent", 9),
        width=["100%", "100%", "50%"],
        height=["50%", "50%", "100%"],
    ),
    bg=rx.color("accent", 10),
    spacing="4",
    padding="1em",
    flex_direction=["column", "column", "row"],
    height="600px",
    width="100%",
)
```

```python test
def test_four_columns_two_narrow(demo):
    row = demo.locator("> .rt-Flex")
    expect(row).to_have_css("flex-direction", "row")
    columns = row.locator("> div")
    expect(columns).to_have_count(4)
    expect(columns.nth(0)).to_have_css("height", "568px")
    expect(columns.nth(1)).to_have_css("height", "568px")
```

## Row

```python demo
rx.flex(
    rx.flex(
        rx.box(bg=rx.color("accent", 3), width=["100%", "100%", "50%"], height="100%"),
        rx.box(bg=rx.color("accent", 5), width=["100%", "100%", "50%"], height="100%"),
        width="100%",
        height="100%",
        spacing="4",
        flex_direction=["column", "column", "row"],
    ),
    rx.box(bg=rx.color("accent", 7), width="100%", height="50%"),
    rx.box(bg=rx.color("accent", 9), width="100%", height="50%"),
    bg=rx.color("accent", 10),
    spacing="4",
    padding="1em",
    flex_direction="column",
    height="600px",
    width="100%",
)
```

```python test
def test_row_above_two_stacked_boxes(demo):
    outer = demo.locator("> .rt-Flex")
    expect(outer).to_have_css("flex-direction", "column")
    expect(outer.locator("> div")).to_have_count(3)
    inner = outer.locator("> .rt-Flex")
    expect(inner).to_have_css("flex-direction", "row")
    expect(inner.locator("> div")).to_have_count(2)
```
