---
components:
  - rx.separator
Separator: |
  lambda **props: rx.separator(**props)
---

```python exec
import reflex as rx
```

# Separator

Visually or semantically separates content.

## Basic Example

```python demo
rx.flex(
    rx.card("Section 1"),
    rx.divider(),
    rx.card("Section 2"),
    spacing="4",
    direction="column",
    align="center",
)
```

```python test
def test_separator_between_cards(demo):
    cards = demo.locator(".rt-Card")
    expect(cards).to_have_text(["Section 1", "Section 2"])
    separator = demo.locator(".rt-Separator")
    top, line, bottom = (
        cards.nth(0).bounding_box(),
        separator.bounding_box(),
        cards.nth(1).bounding_box(),
    )
    assert top["y"] + top["height"] <= line["y"] < bottom["y"]
```

## Size

The `size` prop controls how long the separator is. Using `size="4"` will make
the separator fill the parent container. Setting CSS `width` or `height` prop to `"100%"`
can also achieve this effect, but `size` works the same regardless of the orientation.

```python demo
rx.flex(
    rx.card("Section 1"),
    rx.divider(size="4"),
    rx.card("Section 2"),
    spacing="4",
    direction="column",
)
```

```python test
def test_separator_size_fills_parent(demo):
    expect(demo.locator(".rt-Card")).to_have_text(["Section 1", "Section 2"])
    separator = demo.locator(".rt-Separator")
    expect(separator).to_have_class(re.compile(r"\brt-r-size-4\b"))
    assert separator.bounding_box()["width"] == pytest.approx(
        separator.locator("..").bounding_box()["width"], abs=1
    )
```

## Orientation

Setting the orientation prop to `vertical` will make the separator appear vertically.

```python demo
rx.flex(
    rx.card("Section 1"),
    rx.divider(orientation="vertical", size="4"),
    rx.card("Section 2"),
    spacing="4",
    width="100%",
    height="10vh",
)
```

```python test
def test_separator_vertical(demo):
    cards = demo.locator(".rt-Card")
    expect(cards).to_have_text(["Section 1", "Section 2"])
    separator = demo.locator(".rt-Separator")
    expect(separator).to_have_class(re.compile(r"\brt-r-orientation-vertical\b"))
    left, line, right = (
        cards.nth(0).bounding_box(),
        separator.bounding_box(),
        cards.nth(1).bounding_box(),
    )
    assert left["x"] + left["width"] <= line["x"] < right["x"]
    assert line["height"] == pytest.approx(
        separator.locator("..").bounding_box()["height"], abs=1
    )
```
