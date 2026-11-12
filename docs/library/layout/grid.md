---
components:
  - rx.grid

Grid: |
  lambda **props: rx.grid(
      rx.card("Card 1", size="2", width="5rem"),
      rx.card("Card 2", size="2", width="5rem"),
      rx.card("Card 3", size="2", width="5rem"),
      rx.card("Card 4", size="2", width="5rem"),
      rx.card("Card 5", size="2", width="5rem"),
      rx.card("Card 6", size="2", width="5rem"),
      columns="3",
      gap="0.75rem",
      width="100%",
      min_height="10rem",
      border="1px dashed var(--gray-7)",
      border_radius="0.5rem",
      padding="0.75rem",
      **props,
  )
---

```python exec
import reflex as rx
```

# Grid

Component for creating grid layouts. Either `rows` or `columns` may be specified.

## Basic Example

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
    cards = demo.locator(".rt-Card")
    expect(cards).to_have_text([f"Card {i}" for i in range(1, 13)])
    rects = [cards.nth(i).bounding_box() for i in range(12)]
    # Cards fill rows left to right: three per row, four rows.
    assert len({rect["x"] for rect in rects}) == 3
    assert len({rect["y"] for rect in rects}) == 4
    assert rects[1]["y"] == rects[0]["y"]
    assert rects[3]["x"] == rects[0]["x"]
```

```python demo
rx.grid(
    rx.foreach(
        rx.Var.range(12),
        lambda i: rx.card(f"Card {i + 1}", height="10vh"),
    ),
    rows="3",
    flow="column",
    justify="between",
    spacing="4",
    width="100%",
)
```

```python test
def test_grid_three_rows_column_flow(demo):
    cards = demo.locator(".rt-Card")
    expect(cards).to_have_text([f"Card {i}" for i in range(1, 13)])
    rects = [cards.nth(i).bounding_box() for i in range(12)]
    # Cards fill columns top to bottom: three per column, four columns.
    assert len({rect["y"] for rect in rects}) == 3
    assert len({rect["x"] for rect in rects}) == 4
    assert rects[1]["x"] == rects[0]["x"]
    assert rects[3]["y"] == rects[0]["y"]
```
