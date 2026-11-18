---
components:
  - rx.inset

Inset: |
  lambda **props: rx.card(
      rx.inset(
          rx.image(src="https://web.reflex-assets.dev/other/reflex_banner.png", alt='Reflex banner image', height="auto"),
          **props,
      ),
      width="500px",
  )
---

```python exec
import reflex as rx
```

# Inset

Applies a negative margin to allow content to bleed into the surrounding container.

## Basic Example

Nesting an Inset component inside a Card will render the content from edge to edge of the card.

```python demo
rx.card(
    rx.inset(
        rx.image(
            src="https://web.reflex-assets.dev/other/reflex_banner.png",
            alt="Reflex banner image",
            width="100%",
            height="auto",
        ),
        side="top",
        pb="current",
    ),
    rx.text(
        "Reflex is a web framework that allows developers to build their app in pure Python."
    ),
    width="25vw",
)
```

```python test
def test_inset_top_bleeds_to_card_edges(demo):
    card, inset = demo.locator(".rt-Card"), demo.locator(".rt-Inset")
    expect(inset.get_by_role("img", name="Reflex banner image")).to_have_count(1)
    expect(card.get_by_text("Reflex is a web framework")).to_be_visible()
    outer, inner = card.bounding_box(), inset.bounding_box()
    assert inner["y"] == pytest.approx(outer["y"], abs=2)
    assert inner["x"] == pytest.approx(outer["x"], abs=2)
    assert inner["width"] == pytest.approx(outer["width"], abs=2)
```

## Other Directions

The `side` prop controls which side the negative margin is applied to. When using a specific side,
it is helpful to set the padding for the opposite side to `current` to retain the same padding the
content would have had if it went to the edge of the parent component.

```python demo
rx.card(
    rx.text("The inset below uses a bottom side."),
    rx.inset(
        rx.image(
            src="https://web.reflex-assets.dev/other/reflex_banner.png",
            alt="Reflex banner image",
            width="100%",
            height="auto",
        ),
        side="bottom",
        pt="current",
    ),
    width="25vw",
)
```

```python test
def test_inset_bottom_bleeds_to_card_edges(demo):
    card, inset = demo.locator(".rt-Card"), demo.locator(".rt-Inset")
    expect(inset.get_by_role("img", name="Reflex banner image")).to_have_count(1)
    expect(card.get_by_text("The inset below uses a bottom side.")).to_be_visible()
    outer, inner = card.bounding_box(), inset.bounding_box()
    assert inner["y"] + inner["height"] == pytest.approx(
        outer["y"] + outer["height"], abs=2
    )
    assert inner["x"] == pytest.approx(outer["x"], abs=2)
    assert inner["width"] == pytest.approx(outer["width"], abs=2)
```

```python demo
rx.card(
    rx.flex(
        rx.text(
            "This inset uses a right side, which requires a flex with direction row."
        ),
        rx.inset(
            rx.box(
                background="center/cover url('https://web.reflex-assets.dev/other/reflex_banner.png')",
                height="100%",
            ),
            width="100%",
            side="right",
            pl="current",
        ),
        direction="row",
        width="100%",
    ),
    width="25vw",
)
```

```python test
def test_inset_right_bleeds_to_card_edges(demo):
    card, inset = demo.locator(".rt-Card"), demo.locator(".rt-Inset")
    expect(card.get_by_text("This inset uses a right side")).to_be_visible()
    outer, inner = card.bounding_box(), inset.bounding_box()
    assert inner["x"] + inner["width"] == pytest.approx(
        outer["x"] + outer["width"], abs=2
    )
    assert inner["y"] == pytest.approx(outer["y"], abs=2)
    assert inner["height"] == pytest.approx(outer["height"], abs=2)
```

```python demo
rx.card(
    rx.flex(
        rx.inset(
            rx.box(
                background="center/cover url('https://web.reflex-assets.dev/other/reflex_banner.png')",
                height="100%",
            ),
            width="100%",
            side="left",
            pr="current",
        ),
        rx.text(
            "This inset uses a left side, which also requires a flex with direction row."
        ),
        direction="row",
        width="100%",
    ),
    width="25vw",
)
```

```python test
def test_inset_left_bleeds_to_card_edges(demo):
    card, inset = demo.locator(".rt-Card"), demo.locator(".rt-Inset")
    expect(card.get_by_text("This inset uses a left side")).to_be_visible()
    outer, inner = card.bounding_box(), inset.bounding_box()
    assert inner["x"] == pytest.approx(outer["x"], abs=2)
    assert inner["y"] == pytest.approx(outer["y"], abs=2)
    assert inner["height"] == pytest.approx(outer["height"], abs=2)
```
