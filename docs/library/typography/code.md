---
components:
  - rx.code
meta_description: "Display inline code in Python with Reflex. The rx.code component renders monospaced code text with variants and color schemes, all in pure Python."
---

```python exec
import reflex as rx
```

# Code

```python demo
rx.code("console.log()")
```

```python test
def test_code_renders_inline_code(demo):
    expect(demo.get_by_role("code")).to_have_text("console.log()")
```

## Size

Use the `size` prop to control text size. This prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.code("console.log()", size="1"),
    rx.code("console.log()", size="2"),
    rx.code("console.log()", size="3"),
    rx.code("console.log()", size="4"),
    rx.code("console.log()", size="5"),
    rx.code("console.log()", size="6"),
    rx.code("console.log()", size="7"),
    rx.code("console.log()", size="8"),
    rx.code("console.log()", size="9"),
    direction="column",
    spacing="3",
    align="start",
)
```

```python test
def test_code_sizes_increase(demo):
    codes = demo.get_by_role("code")
    expect(codes).to_have_count(9)
    expect(codes).to_have_text(["console.log()"] * 9)
    sizes = codes.evaluate_all(
        "els => els.map(e => parseFloat(getComputedStyle(e).fontSize))"
    )
    assert sizes == sorted(set(sizes))
```

## Weight

Use the `weight` prop to set the text weight.

```python demo
rx.flex(
    rx.code("console.log()", weight="light"),
    rx.code("console.log()", weight="regular"),
    rx.code("console.log()", weight="medium"),
    rx.code("console.log()", weight="bold"),
    direction="column",
    spacing="3",
)
```

```python test
def test_code_weights(demo):
    codes = demo.get_by_role("code")
    expect(codes).to_have_count(4)
    for i, weight in enumerate(["300", "400", "500", "700"]):
        expect(codes.nth(i)).to_have_css("font-weight", weight)
```

## Variant

Use the `variant` prop to control the visual style.

```python demo
rx.flex(
    rx.code("console.log()", variant="solid"),
    rx.code("console.log()", variant="soft"),
    rx.code("console.log()", variant="outline"),
    rx.code("console.log()", variant="ghost"),
    direction="column",
    spacing="2",
    align="start",
)
```

```python test
def test_code_variants(demo):
    codes = demo.get_by_role("code")
    expect(codes).to_have_count(4)
    for i, variant in enumerate(["solid", "soft", "outline", "ghost"]):
        expect(codes.nth(i)).to_have_class(re.compile(rf"\brt-variant-{variant}\b"))
    expect(codes.last).to_have_css("background-color", "rgba(0, 0, 0, 0)")
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.code("console.log()", color_scheme="indigo"),
    rx.code("console.log()", color_scheme="crimson"),
    rx.code("console.log()", color_scheme="orange"),
    rx.code("console.log()", color_scheme="cyan"),
    direction="column",
    spacing="2",
    align="start",
)
```

```python test
def test_code_color_schemes(demo):
    codes = demo.get_by_role("code")
    expect(codes).to_have_count(4)
    for i, color in enumerate(["indigo", "crimson", "orange", "cyan"]):
        expect(codes.nth(i)).to_have_attribute("data-accent-color", color)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.flex(
        rx.code("console.log()", variant="solid"),
        rx.code("console.log()", variant="soft"),
        rx.code("console.log()", variant="outline"),
        rx.code("console.log()", variant="ghost"),
        direction="column",
        align="start",
        spacing="2",
    ),
    rx.flex(
        rx.code("console.log()", variant="solid", high_contrast=True),
        rx.code("console.log()", variant="soft", high_contrast=True),
        rx.code("console.log()", variant="outline", high_contrast=True),
        rx.code("console.log()", variant="ghost", high_contrast=True),
        direction="column",
        align="start",
        spacing="2",
    ),
    spacing="3",
)
```

```python test
def test_code_high_contrast_column(demo):
    codes = demo.get_by_role("code")
    expect(codes).to_have_count(8)
    high_contrast = re.compile(r"\brt-high-contrast\b")
    for i in range(4):
        expect(codes.nth(i)).not_to_have_class(high_contrast)
        expect(codes.nth(i + 4)).to_have_class(high_contrast)
    # The two columns sit side by side.
    assert codes.nth(4).bounding_box()["x"] > codes.nth(0).bounding_box()["x"]
```
