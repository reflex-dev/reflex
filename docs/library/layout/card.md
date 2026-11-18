---
components:
  - rx.card

Card: |
  lambda **props: rx.card("Basic Card ", **props)
---

```python exec
import reflex as rx
```

# Card

A Card component is used for grouping related components. It is similar to the Box, except it has a
border, uses the theme colors and border radius, and provides a `size` prop to control spacing
and margin according to the Radix `"1"` - `"5"` scale.

The Card requires less styling than a Box to achieve consistent visual results when used with
themes.

## Basic Example

```python demo
rx.flex(
    rx.card("Card 1", size="1"),
    rx.card("Card 2", size="2"),
    rx.card("Card 3", size="3"),
    rx.card("Card 4", size="4"),
    rx.card("Card 5", size="5"),
    spacing="2",
    align_items="flex-start",
    flex_wrap="wrap",
)
```

```python test
def test_card_sizes(demo):
    cards = demo.locator(".rt-Card")
    expect(cards).to_have_text([f"Card {i}" for i in range(1, 6)])
    for i in range(5):
        expect(cards.nth(i)).to_have_class(re.compile(rf"\brt-r-size-{i + 1}\b"))
    paddings = cards.evaluate_all(
        "els => els.map(e => parseFloat(getComputedStyle(e).paddingTop))"
    )
    assert paddings == sorted(set(paddings))
```

## Rendering as a Different Element

The `as_child` prop may be used to render the Card as a different element. Link and Button are
commonly used to make a Card clickable.

```python demo
rx.card(
    rx.link(
        rx.flex(
            rx.avatar(src="https://web.reflex-assets.dev/other/reflex_banner.png"),
            rx.box(
                rx.heading("Quick Start", as_="h2"),
                rx.text("Get started with Reflex in 5 minutes."),
            ),
            spacing="2",
        ),
    ),
    as_child=True,
)
```

```python test
def test_card_as_child_link(demo):
    card = demo.locator("a.rt-Card")
    expect(card).to_have_count(1)
    expect(card.get_by_role("heading", level=2)).to_have_text("Quick Start")
    expect(card.get_by_text("Get started with Reflex in 5 minutes.")).to_be_visible()
```

## Using Inset Content
