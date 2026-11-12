---
components:
  - rx.spacer
---

```python exec
import reflex as rx
```

# Spacer

Creates an adjustable, empty space that can be used to tune the spacing between child elements within `flex`.

```python demo
rx.flex(
    rx.center(rx.text("Example"), bg="lightblue", color="black"),
    rx.spacer(),
    rx.center(rx.text("Example"), bg="lightgreen", color="black"),
    rx.spacer(),
    rx.center(rx.text("Example"), bg="salmon", color="black"),
    width="100%",
)
```

```python test
def test_spacer_pushes_items_apart(demo):
    items = demo.get_by_text("Example", exact=True)
    expect(items).to_have_count(3)
    row = items.first.locator("../..").bounding_box()
    first, middle, last = (items.nth(i).locator("..").bounding_box() for i in range(3))
    assert first["x"] == pytest.approx(row["x"], abs=1)
    assert last["x"] + last["width"] == pytest.approx(row["x"] + row["width"], abs=1)
    assert middle["x"] + middle["width"] / 2 == pytest.approx(
        row["x"] + row["width"] / 2, abs=2
    )
```

As `stack`, `vstack` and `hstack` are all built from `flex`, it is possible to also use `spacer` inside of these components.
