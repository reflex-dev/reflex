---
components:
  - rx.callout.root
  - rx.callout.icon
  - rx.callout.text
---

```python exec
import reflex as rx
```

# Callout

A `callout` is a short message to attract user's attention.

```python demo
rx.callout.root(
    rx.callout.icon(rx.icon(tag="info")),
    rx.callout.text(
        "You will need admin privileges to install and access this application."
    ),
)
```

```python test
def test_callout_root_shows_icon_and_text(demo):
    callout = demo.locator(".rt-CalloutRoot")
    expect(callout.locator(".rt-CalloutText")).to_have_text(
        "You will need admin privileges to install and access this application."
    )
    expect(callout.locator(".rt-CalloutIcon svg.lucide-info")).to_be_visible()
```

The `callout` component is made up of a `callout.root`, which groups `callout.icon` and `callout.text` parts. This component is based on the `div` element and supports common margin props.

The `callout.icon` provides width and height for the `icon` associated with the `callout`. This component is based on the `div` element. See the [**icon** component for all icons that are available.](/docs/library/data-display/icon/)

The `callout.text` renders the callout text. This component is based on the `p` element.

## As alert

```python demo
rx.callout.root(
    rx.callout.icon(rx.icon(tag="triangle_alert")),
    rx.callout.text(
        "Access denied. Please contact the network administrator to view this page."
    ),
    color_scheme="red",
    role="alert",
)
```

```python test
def test_callout_root_as_alert(demo):
    alert = demo.get_by_role("alert")
    expect(alert).to_have_text(
        "Access denied. Please contact the network administrator to view this page."
    )
    expect(alert).to_have_attribute("data-accent-color", "red")
    expect(alert.locator("svg.lucide-triangle-alert")).to_be_visible()
```

## Style

### Size

Use the `size` prop to control the size.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        size="3",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        size="2",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        size="1",
    ),
    direction="column",
    spacing="3",
    align="start",
)
```

```python test
def test_callout_root_sizes(demo):
    callouts = demo.locator(".rt-CalloutRoot")
    expect(callouts).to_have_count(3)
    for i, size in enumerate(["3", "2", "1"]):
        expect(callouts.nth(i)).to_have_class(re.compile(rf"\brt-r-size-{size}\b"))
```

### Variant

Use the `variant` prop to control the visual style. It is set to `soft` by default.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        variant="soft",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        variant="surface",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        variant="outline",
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_callout_root_variants(demo):
    callouts = demo.locator(".rt-CalloutRoot")
    expect(callouts).to_have_count(3)
    for i, variant in enumerate(["soft", "surface", "outline"]):
        expect(callouts.nth(i)).to_have_class(re.compile(rf"\brt-variant-{variant}\b"))
```

### Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        color_scheme="blue",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        color_scheme="green",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        color_scheme="red",
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_callout_root_colors(demo):
    callouts = demo.locator(".rt-CalloutRoot")
    expect(callouts).to_have_count(3)
    for i, color in enumerate(["blue", "green", "red"]):
        expect(callouts.nth(i)).to_have_attribute("data-accent-color", color)
```

### High Contrast

Use the `high_contrast` prop to add additional contrast.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text(
            "You will need admin privileges to install and access this application."
        ),
        high_contrast=True,
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_callout_root_high_contrast(demo):
    expect(demo.locator(".rt-CalloutText")).to_have_text(
        ["You will need admin privileges to install and access this application."] * 2
    )
    expect(demo.locator(".rt-CalloutRoot.rt-high-contrast")).to_have_count(1)
```
