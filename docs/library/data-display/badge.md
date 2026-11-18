---
components:
  - rx.badge

Badge: |
  lambda **props: rx.badge("Basic Badge", **props)
---

# Badge

```python exec
import reflex as rx
```

Badges are used to highlight an item's status for quick recognition.

## Basic Example

To create a badge component with only text inside, pass the text as an argument.

```python demo
rx.badge("New")
```

```python test
def test_badge_text(demo):
    expect(demo.locator(".rt-Badge")).to_have_text("New")
```

## Styling


### Size

The `size` prop controls the size and padding of a badge. It can take values of `"1" | "2"`, with default being `"1"`.

```python demo
rx.flex(
    rx.badge("New"),
    rx.badge("New", size="1"),
    rx.badge("New", size="2"),
    align="center",
    spacing="2",
)
```

```python test
def test_badge_sizes(demo):
    badges = demo.locator(".rt-Badge")
    expect(badges).to_have_text(["New", "New", "New"])
    expect(demo.locator(".rt-Badge.rt-r-size-2")).to_have_count(1)
```

### Variant

The `variant` prop controls the visual style of the badge. The supported variant types are `"solid" | "soft" | "surface" | "outline"`. The variant default is `"soft"`.

```python demo
rx.flex(
    rx.badge("New", variant="solid"),
    rx.badge("New", variant="soft"),
    rx.badge("New"),
    rx.badge("New", variant="surface"),
    rx.badge("New", variant="outline"),
    spacing="2",
)
```

```python test
def test_badge_variants(demo):
    for variant, count in [("solid", 1), ("soft", 2), ("surface", 1), ("outline", 1)]:
        expect(demo.locator(f".rt-Badge.rt-variant-{variant}")).to_have_count(count)
```

### Color Scheme

The `color_scheme` prop sets a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.badge("New", color_scheme="indigo"),
    rx.badge("New", color_scheme="cyan"),
    rx.badge("New", color_scheme="orange"),
    rx.badge("New", color_scheme="crimson"),
    spacing="2",
)
```

```python test
def test_badge_color_schemes(demo):
    badges = demo.locator(".rt-Badge")
    expect(badges).to_have_count(4)
    for i, color in enumerate(["indigo", "cyan", "orange", "crimson"]):
        expect(badges.nth(i)).to_have_attribute("data-accent-color", color)
```

### High Contrast

The `high_contrast` prop increases color contrast of the fallback text with the background.

```python demo
rx.flex(
    rx.flex(
        rx.badge("New", variant="solid"),
        rx.badge("New", variant="soft"),
        rx.badge("New", variant="surface"),
        rx.badge("New", variant="outline"),
        spacing="2",
    ),
    rx.flex(
        rx.badge("New", variant="solid", high_contrast=True),
        rx.badge("New", variant="soft", high_contrast=True),
        rx.badge("New", variant="surface", high_contrast=True),
        rx.badge("New", variant="outline", high_contrast=True),
        spacing="2",
    ),
    direction="column",
    spacing="2",
)
```

```python test
def test_badge_high_contrast(demo):
    expect(demo.locator(".rt-Badge")).to_have_count(8)
    expect(demo.locator(".rt-Badge.rt-high-contrast")).to_have_count(4)
```

### Radius

The `radius` prop sets specific radius value, ignoring the global theme. It can take values `"none" | "small" | "medium" | "large" | "full"`.

```python demo
rx.flex(
    rx.badge("New", radius="none"),
    rx.badge("New", radius="small"),
    rx.badge("New", radius="medium"),
    rx.badge("New", radius="large"),
    rx.badge("New", radius="full"),
    spacing="3",
)
```

```python test
def test_badge_radius(demo):
    badges = demo.locator(".rt-Badge")
    expect(badges).to_have_count(5)
    for i, radius in enumerate(["none", "small", "medium", "large", "full"]):
        expect(badges.nth(i)).to_have_attribute("data-radius", radius)
```

## Final Example

A badge may contain more complex elements within it. This example uses a `flex` component to align an icon and the text correctly, using the `gap` prop to
ensure a comfortable spacing between the two.

```python demo
rx.badge(
    rx.flex(
        rx.icon(tag="arrow_up"),
        rx.text("8.8%"),
        spacing="1",
    ),
    color_scheme="grass",
)
```

```python test
def test_badge_with_icon(demo):
    badge = demo.locator(".rt-Badge")
    expect(badge).to_have_text("8.8%")
    expect(badge).to_have_attribute("data-accent-color", "grass")
    expect(badge.locator("svg.lucide-arrow-up")).to_be_visible()
```
