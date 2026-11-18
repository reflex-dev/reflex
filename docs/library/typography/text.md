---
components:
  - rx.text
  - rx.text.em
---

```python exec
import reflex as rx
```

# Text

```python demo
rx.text("The quick brown fox jumps over the lazy dog.")
```

```python test
def test_text_renders_paragraph(demo):
    expect(demo.locator("p")).to_have_text(
        "The quick brown fox jumps over the lazy dog."
    )
```

## As another element

Use the `as_` prop to render text as a `p`, `label`, `div` or `span`. This prop is purely semantic and does not alter visual appearance.

```python demo
rx.flex(
    rx.text("This is a ", rx.text.strong("paragraph"), " element.", as_="p"),
    rx.text("This is a ", rx.text.strong("label"), " element.", as_="label"),
    rx.text("This is a ", rx.text.strong("div"), " element.", as_="div"),
    rx.text("This is a ", rx.text.strong("span"), " element.", as_="span"),
    direction="column",
    spacing="3",
)
```

```python test
def test_text_as_other_elements(demo):
    for tag in ["p", "label", "div", "span"]:
        element = demo.locator(f"{tag}.rt-Text")
        expect(element).to_have_text(
            f"This is a {'paragraph' if tag == 'p' else tag} element."
        )
```

## Size

Use the `size` prop to control text size. This prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.text("The quick brown fox jumps over the lazy dog.", size="1"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="2"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="3"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="4"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="5"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="6"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="7"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="8"),
    rx.text("The quick brown fox jumps over the lazy dog.", size="9"),
    direction="column",
    spacing="3",
)
```

```python test
def test_text_sizes_increase(demo):
    texts = demo.locator("p")
    expect(texts).to_have_count(9)
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
        expect(texts.nth(i)).to_have_css("font-size", px)
```

Sizes 2–4 are designed to work well for long-form content. Sizes 1–3 are designed to work well for UI labels.

## Weight

Use the `weight` prop to set the text weight.

```python demo
rx.flex(
    rx.text("The quick brown fox jumps over the lazy dog.", weight="light", as_="div"),
    rx.text(
        "The quick brown fox jumps over the lazy dog.", weight="regular", as_="div"
    ),
    rx.text("The quick brown fox jumps over the lazy dog.", weight="medium", as_="div"),
    rx.text("The quick brown fox jumps over the lazy dog.", weight="bold", as_="div"),
    direction="column",
    spacing="3",
)
```

```python test
def test_text_weights(demo):
    texts = demo.locator("div.rt-Text")
    expect(texts).to_have_count(4)
    for i, weight in enumerate(["300", "400", "500", "700"]):
        expect(texts.nth(i)).to_have_css("font-weight", weight)
```

## Align

Use the `align` prop to set text alignment.

```python demo
rx.flex(
    rx.text("Left-aligned", align="left", as_="div"),
    rx.text("Center-aligned", align="center", as_="div"),
    rx.text("Right-aligned", align="right", as_="div"),
    direction="column",
    spacing="3",
    width="100%",
)
```

```python test
def test_text_alignment(demo):
    for name, align in [("Left", "left"), ("Center", "center"), ("Right", "right")]:
        expect(demo.get_by_text(f"{name}-aligned")).to_have_css("text-align", align)
```

## Trim

Use the `trim` prop to trim the leading space at the start, end, or both sides of the text box.

```python demo
rx.flex(
    rx.text(
        "Without Trim",
        trim="normal",
        style={
            "background": "var(--gray-a2)",
            "border_top": "1px dashed var(--gray-a7)",
            "border_bottom": "1px dashed var(--gray-a7)",
        },
    ),
    rx.text(
        "With Trim",
        trim="both",
        style={
            "background": "var(--gray-a2)",
            "border_top": "1px dashed var(--gray-a7)",
            "border_bottom": "1px dashed var(--gray-a7)",
        },
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_text_trim_shrinks_box(demo):
    plain = demo.get_by_text("Without Trim")
    trimmed = demo.get_by_text("With Trim")
    expect(plain).to_have_class(re.compile(r"\brt-r-lt-normal\b"))
    expect(trimmed).to_have_class(re.compile(r"\brt-r-lt-both\b"))
    assert trimmed.bounding_box()["height"] < plain.bounding_box()["height"]
```

Trimming the leading is useful when dialing in vertical spacing in cards or other “boxy” components. Otherwise, padding looks larger on top and bottom than on the sides.

```python demo
rx.flex(
    rx.box(
        rx.heading(
            "Without trim",
            as_="h2",
            margin_bottom="4px",
            size="3",
        ),
        rx.text(
            "The goal of typography is to relate font size, line height, and line width in a proportional way that maximizes beauty and makes reading easier and more pleasant."
        ),
        style={
            "background": "var(--gray-a2)",
            "border": "1px dashed var(--gray-a7)",
        },
        padding="16px",
    ),
    rx.box(
        rx.heading("With trim", as_="h2", margin_bottom="4px", size="3", trim="start"),
        rx.text(
            "The goal of typography is to relate font size, line height, and line width in a proportional way that maximizes beauty and makes reading easier and more pleasant."
        ),
        style={
            "background": "var(--gray-a2)",
            "border": "1px dashed var(--gray-a7)",
        },
        padding="16px",
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_text_trim_start_heading_in_box(demo):
    untrimmed = demo.get_by_role("heading", name="Without trim")
    trimmed = demo.get_by_role("heading", name="With trim")
    expect(trimmed).to_have_class(re.compile(r"\brt-r-lt-start\b"))
    expect(demo.locator("p")).to_have_count(2)
    assert trimmed.bounding_box()["height"] < untrimmed.bounding_box()["height"]
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.text("The quick brown fox jumps over the lazy dog.", color_scheme="indigo"),
    rx.text("The quick brown fox jumps over the lazy dog.", color_scheme="cyan"),
    rx.text("The quick brown fox jumps over the lazy dog.", color_scheme="crimson"),
    rx.text("The quick brown fox jumps over the lazy dog.", color_scheme="orange"),
    direction="column",
)
```

```python test
def test_text_color_schemes(demo):
    texts = demo.locator("p")
    expect(texts).to_have_count(4)
    for i, color in enumerate(["indigo", "cyan", "crimson", "orange"]):
        expect(texts.nth(i)).to_have_attribute("data-accent-color", color)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.text(
        "The quick brown fox jumps over the lazy dog.",
        color_scheme="indigo",
        high_contrast=True,
    ),
    rx.text(
        "The quick brown fox jumps over the lazy dog.",
        color_scheme="cyan",
        high_contrast=True,
    ),
    rx.text(
        "The quick brown fox jumps over the lazy dog.",
        color_scheme="crimson",
        high_contrast=True,
    ),
    rx.text(
        "The quick brown fox jumps over the lazy dog.",
        color_scheme="orange",
        high_contrast=True,
    ),
    direction="column",
)
```

```python test
def test_text_high_contrast_colors(demo):
    texts = demo.locator("p")
    expect(texts).to_have_count(4)
    for i, color in enumerate(["indigo", "cyan", "crimson", "orange"]):
        expect(texts.nth(i)).to_have_attribute("data-accent-color", color)
        expect(texts.nth(i)).to_have_class(re.compile(r"\brt-high-contrast\b"))
```

## With formatting

Compose `Text` with formatting components to add emphasis and structure to content.

```python demo
rx.text(
    "Look, such a helpful ",
    rx.link("link", href="#"),
    ", an ",
    rx.text.em("italic emphasis"),
    " a piece of computer ",
    rx.code("code"),
    ", and even a hotkey combination ",
    rx.text.kbd("⇧⌘A"),
    " within the text.",
    size="5",
)
```

```python test
def test_text_with_formatting(demo):
    paragraph = demo.locator("p")
    expect(paragraph).to_have_text(
        "Look, such a helpful link, an italic emphasis a piece of computer code,"
        " and even a hotkey combination ⇧⌘A within the text."
    )
    expect(paragraph).to_have_css("font-size", "20px")
    expect(paragraph.get_by_role("link")).to_have_text("link")
    expect(paragraph.locator("em")).to_have_text("italic emphasis")
    expect(paragraph.locator("code")).to_have_text("code")
    expect(paragraph.locator("kbd")).to_have_text("⇧⌘A")
```

## Preformmatting

By Default, the browser renders multiple white spaces into one. To preserve whitespace, use the `white_space = "pre"` css prop.

```python demo
rx.hstack(
    rx.text("This is not pre     formatted"),
    rx.text("This is pre     formatted", white_space="pre"),
)
```

```python test
def test_text_white_space_pre(demo):
    texts = demo.locator("p")
    expect(texts.first).to_have_css("white-space", "normal")
    expect(texts.last).to_have_css("white-space", "pre")
    assert texts.last.inner_text() == "This is pre     formatted"
    assert texts.first.inner_text() == "This is not pre formatted"
```

## With form controls

Composing `text` with a form control like `checkbox`, `radiogroup`, or `switch` automatically centers the control with the first line of text, even when the text is multi-line.

```python demo
rx.box(
    rx.text(
        rx.flex(
            rx.checkbox(default_checked=True),
            "I understand that these documents are confidential and cannot be shared with a third party.",
        ),
        as_="label",
        size="3",
    ),
    style={"max_width": 300},
)
```

```python test
def test_text_label_toggles_checkbox(demo):
    checkbox = demo.get_by_role("checkbox")
    expect(checkbox).to_be_checked()
    label = demo.locator("label").first
    expect(label).to_have_text(
        "I understand that these documents are confidential and cannot be shared"
        " with a third party."
    )
    label.click()
    expect(checkbox).not_to_be_checked()
```
