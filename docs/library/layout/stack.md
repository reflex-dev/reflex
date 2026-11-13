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

VStack: |
  lambda **props: rx.vstack(
      rx.card("Card 1", size="2"),
      rx.card("Card 2", size="2"),
      rx.card("Card 3", size="2"),
      width="100%",
      border_radius="0.5rem",
      **props,
  )

HStack: |
  lambda **props: rx.hstack(
      rx.card("Card 1", size="2"),
      rx.card("Card 2", size="2"),
      rx.card("Card 3", size="2"),
      width="100%",
      border_radius="0.5rem",
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
            color="black",
            border_radius="3px",
            width="20%",
        ),
        rx.box(
            "Example",
            bg="lightblue",
            color="black",
            border_radius="3px",
            width="30%",
        ),
        rx.box(
            "Example",
            bg="lightgreen",
            color="black",
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
            color="black",
            border_radius="3px",
            width="20%",
        ),
        rx.box(
            "Example",
            bg="lightblue",
            color="black",
            border_radius="3px",
            width="30%",
        ),
        rx.box(
            "Example",
            bg="lightgreen",
            color="black",
            border_radius="3px",
            width="50%",
        ),
        flex_direction="column",
        width="100%",
    ),
    width="100%",
)
```

```python test
def test_stack_row_and_column(demo):
    boxes = demo.get_by_text("Example", exact=True)
    expect(boxes).to_have_count(6)
    rects = [boxes.nth(i).bounding_box() for i in range(6)]
    row, column = rects[:3], rects[3:]
    assert len({rect["y"] for rect in row}) == 1
    assert [rect["x"] for rect in row] == sorted({rect["x"] for rect in row})
    assert len({rect["x"] for rect in column}) == 1
    assert [rect["y"] for rect in column] == sorted({rect["y"] for rect in column})
```

## Hstack

```python demo
rx.hstack(
    rx.box("Example", bg="red", color="black", border_radius="3px", width="10%"),
    rx.box(
        "Example",
        bg="orange",
        color="black",
        border_radius="3px",
        width="10%",
    ),
    rx.box(
        "Example",
        bg="yellow",
        color="black",
        border_radius="3px",
        width="10%",
    ),
    rx.box(
        "Example",
        bg="lightblue",
        color="black",
        border_radius="3px",
        width="10%",
    ),
    rx.box(
        "Example",
        bg="lightgreen",
        color="black",
        border_radius="3px",
        width="60%",
    ),
    width="100%",
)
```

```python test
def test_hstack_lays_out_horizontally(demo):
    boxes = demo.get_by_text("Example", exact=True)
    expect(boxes).to_have_count(5)
    rects = [boxes.nth(i).bounding_box() for i in range(5)]
    assert [rect["x"] for rect in rects] == sorted({rect["x"] for rect in rects})
    # Side by side: every box shares vertical space with the first.
    first = rects[0]
    for rect in rects:
        assert rect["y"] < first["y"] + first["height"]
        assert first["y"] < rect["y"] + rect["height"]
    # The 60% box is the widest; the 10% boxes keep their text's minimum width.
    assert rects[4]["width"] > max(rect["width"] for rect in rects[:4])
```

## Vstack

```python demo
rx.vstack(
    rx.box("Example", bg="red", color="black", border_radius="3px", width="20%"),
    rx.box(
        "Example",
        bg="orange",
        color="black",
        border_radius="3px",
        width="40%",
    ),
    rx.box(
        "Example",
        bg="yellow",
        color="black",
        border_radius="3px",
        width="60%",
    ),
    rx.box(
        "Example",
        bg="lightblue",
        color="black",
        border_radius="3px",
        width="80%",
    ),
    rx.box(
        "Example",
        bg="lightgreen",
        color="black",
        border_radius="3px",
        width="100%",
    ),
    width="100%",
)
```

```python test
def test_vstack_lays_out_vertically(demo):
    boxes = demo.get_by_text("Example", exact=True)
    expect(boxes).to_have_count(5)
    rects = [boxes.nth(i).bounding_box() for i in range(5)]
    for above, below in zip(rects, rects[1:]):
        assert below["y"] >= above["y"] + above["height"]
    for i, rect in enumerate(rects):
        assert rect["width"] == pytest.approx((i + 1) * rects[0]["width"], rel=0.02)
```

## Real World Example

```python demo
rx.hstack(
    rx.box(
        rx.heading("Saving Money", as_="h2"),
        rx.text(
            "Saving money is an art that combines discipline, strategic planning, and the wisdom to foresee future needs and emergencies. It begins with the simple act of setting aside a portion of one's income, creating a buffer that can grow over time through interest or investments.",
            margin_top="0.5em",
        ),
        padding="1em",
        border_width="1px",
    ),
    rx.box(
        rx.heading("Spending Money", as_="h2"),
        rx.text(
            "Spending money is a balancing act between fulfilling immediate desires and maintaining long-term financial health. It's about making choices, sometimes indulging in the pleasures of the moment, and at other times, prioritizing essential expenses.",
            margin_top="0.5em",
        ),
        padding="1em",
        border_width="1px",
    ),
    gap="2em",
)
```

```python test
def test_hstack_real_world_columns(demo):
    saving = demo.get_by_role("heading", name="Saving Money", level=2)
    spending = demo.get_by_role("heading", name="Spending Money", level=2)
    expect(demo.get_by_text("Saving money is an art")).to_be_visible()
    expect(demo.get_by_text("Spending money is a balancing act")).to_be_visible()
    assert saving.bounding_box()["y"] == spending.bounding_box()["y"]
    assert spending.bounding_box()["x"] > saving.bounding_box()["x"]
```
