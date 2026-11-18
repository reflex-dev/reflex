---
components:
  - rx.blockquote
meta_description: "Add semantic blockquotes to your Python web app with Reflex. The rx.blockquote component displays quoted text with multiple size and weight options."
---

```python exec
import reflex as rx
```

# Blockquote

```python demo
rx.blockquote("Perfect typography is certainly the most elusive of all arts.")
```

```python test
def test_blockquote_renders_quote(demo):
    expect(demo.get_by_role("blockquote")).to_have_text(
        "Perfect typography is certainly the most elusive of all arts."
    )
```

## Size

Use the `size` prop to control the size of the blockquote. The prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="1"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="2"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="3"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="4"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="5"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="6"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="7"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="8"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", size="9"
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_blockquote_sizes_increase(demo):
    quotes = demo.get_by_role("blockquote")
    expect(quotes).to_have_count(9)
    for i, px in enumerate([
        "12px",
        "14px",
        "16px",
        "18px",
        "20px",
        "24px",
        "28px",
        "35px",
        "60px",
    ]):
        expect(quotes.nth(i)).to_have_css("font-size", px)
```

## Weight

Use the `weight` prop to set the blockquote weight.

```python demo
rx.flex(
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", weight="light"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.",
        weight="regular",
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", weight="medium"
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.", weight="bold"
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_blockquote_weights(demo):
    quotes = demo.get_by_role("blockquote")
    expect(quotes).to_have_count(4)
    for i, weight in enumerate(["300", "400", "500", "700"]):
        expect(quotes.nth(i)).to_have_css("font-weight", weight)
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.",
        color_scheme="indigo",
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.",
        color_scheme="cyan",
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.",
        color_scheme="crimson",
    ),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.",
        color_scheme="orange",
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_blockquote_color_schemes(demo):
    quotes = demo.get_by_role("blockquote")
    expect(quotes).to_have_count(4)
    for i, color in enumerate(["indigo", "cyan", "crimson", "orange"]):
        expect(quotes.nth(i)).to_have_attribute("data-accent-color", color)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.blockquote("Perfect typography is certainly the most elusive of all arts."),
    rx.blockquote(
        "Perfect typography is certainly the most elusive of all arts.",
        high_contrast=True,
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_blockquote_high_contrast(demo):
    quotes = demo.get_by_role("blockquote")
    expect(quotes).to_have_count(2)
    expect(quotes.first).not_to_have_class(re.compile(r"\brt-high-contrast\b"))
    expect(quotes.last).to_have_class(re.compile(r"\brt-high-contrast\b"))
```
