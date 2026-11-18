---
components:
  - rx.link
---

```python exec
import reflex as rx
```

# Link

Links are accessible elements used primarily for navigation. Use the `href` prop to specify the location for the link to navigate to.

```python demo
rx.link("Reflex Home Page.", href="https://reflex.dev/")
```

```python test
def test_link_to_external_url(demo):
    expect(demo.get_by_role("link", name="Reflex Home Page.")).to_have_attribute(
        "href", "https://reflex.dev/"
    )
```

You can also provide local links to other pages in your project without writing the full url.

```python demo
rx.link(
    "Example",
    href="/library/",
)
```

```python test
def test_link_to_local_page(demo):
    expect(demo.get_by_role("link", name="Example")).to_have_attribute(
        "href", "/docs/library/"
    )
```

The `link` component can be used to wrap other components to make them link to other pages.

```python demo
rx.link(rx.button("Example"), href="https://reflex.dev/")
```

```python test
def test_link_wraps_button(demo):
    link = demo.locator("a.rt-Link")
    expect(link).to_have_attribute("href", "https://reflex.dev/")
    expect(link.get_by_role("button")).to_have_text("Example")
```

You can also create anchors to link to specific parts of a page using the `id` prop.

```python demo
rx.box("Example", id="example")
```

```python test
def test_box_is_anchor_target(demo):
    expect(demo.locator("#example")).to_have_text("Example")
```

To reference an anchor, you can use the `href` prop of the `link` component. The `href` should be in the format of the page you want to link to followed by a # and the id of the anchor.

```python demo
rx.link("Example", href="/library/typography/link/#example")
```

```python test
def test_link_jumps_to_anchor(demo, page):
    demo.get_by_role("link", name="Example").click()
    expect(page).to_have_url(re.compile(r"/library/typography/link/#example$"))
```

```md alert info
# Redirecting the user using State

It is also possible to redirect the user to a new path within the application, using `rx.redirect()`. Check out the docs [here](/docs/api-reference/special-events/).
```

## Style

## Size

Use the `size` prop to control the size of the link. The prop also provides correct line height and corrective letter spacing—as text size increases, the relative line height and letter spacing decrease.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", size="1"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="2"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="3"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="4"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="5"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="6"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="7"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="8"),
    rx.link("The quick brown fox jumps over the lazy dog.", size="9"),
    direction="column",
    spacing="3",
)
```

```python test
def test_link_sizes_increase(demo):
    links = demo.locator("a.rt-Link")
    expect(links).to_have_count(9)
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
        expect(links.nth(i)).to_have_css("font-size", px)
```

## Weight

Use the `weight` prop to set the text weight.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", weight="light"),
    rx.link("The quick brown fox jumps over the lazy dog.", weight="regular"),
    rx.link("The quick brown fox jumps over the lazy dog.", weight="medium"),
    rx.link("The quick brown fox jumps over the lazy dog.", weight="bold"),
    direction="column",
    spacing="3",
)
```

```python test
def test_link_weights(demo):
    links = demo.locator("a.rt-Link")
    expect(links).to_have_count(4)
    for i, weight in enumerate(["300", "400", "500", "700"]):
        expect(links.nth(i)).to_have_css("font-weight", weight)
```

## Trim

Use the `trim` prop to trim the leading space at the start, end, or both sides of the rendered text.

```python demo
rx.flex(
    rx.link(
        "Without Trim",
        trim="normal",
        style={
            "background": "var(--gray-a2)",
            "border_top": "1px dashed var(--gray-a7)",
            "border_bottom": "1px dashed var(--gray-a7)",
        },
    ),
    rx.link(
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
def test_link_trim_shrinks_box(demo):
    plain = demo.get_by_text("Without Trim")
    trimmed = demo.get_by_text("With Trim")
    expect(plain).to_have_class(re.compile(r"\brt-r-lt-normal\b"))
    expect(trimmed).to_have_class(re.compile(r"\brt-r-lt-both\b"))
    assert trimmed.bounding_box()["height"] < plain.bounding_box()["height"]
```

## Underline

Use the `underline` prop to manage the visibility of the underline affordance. It defaults to `auto`.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", underline="auto"),
    rx.link("The quick brown fox jumps over the lazy dog.", underline="hover"),
    rx.link("The quick brown fox jumps over the lazy dog.", underline="always"),
    direction="column",
    spacing="3",
)
```

```python test
def test_link_underline_modes(demo):
    links = demo.locator("a.rt-Link")
    expect(links).to_have_count(3)
    expect(links.nth(1)).to_have_css("text-decoration-line", "none")
    expect(links.nth(2)).to_have_css("text-decoration-line", "underline")
    links.nth(1).hover()
    expect(links.nth(1)).to_have_css("text-decoration-line", "underline")
```

## Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="indigo"),
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="cyan"),
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="crimson"),
    rx.link("The quick brown fox jumps over the lazy dog.", color_scheme="orange"),
    direction="column",
)
```

```python test
def test_link_color_schemes(demo):
    links = demo.locator("a.rt-Link")
    expect(links).to_have_count(4)
    for i, color in enumerate(["indigo", "cyan", "crimson", "orange"]):
        expect(links.nth(i)).to_have_attribute("data-accent-color", color)
```

## High Contrast

Use the `high_contrast` prop to increase color contrast with the background.

```python demo
rx.flex(
    rx.link("The quick brown fox jumps over the lazy dog."),
    rx.link("The quick brown fox jumps over the lazy dog.", high_contrast=True),
    direction="column",
)
```

```python test
def test_link_high_contrast(demo):
    links = demo.locator("a.rt-Link")
    expect(links).to_have_count(2)
    expect(links.first).not_to_have_class(re.compile(r"\brt-high-contrast\b"))
    expect(links.last).to_have_class(re.compile(r"\brt-high-contrast\b"))
```
