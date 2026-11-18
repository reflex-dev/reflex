---
components:
  - rx.callout

Callout: |
  lambda **props: rx.callout("Basic Callout", icon="search", **props)

CalloutRoot: |
  lambda **props: rx.callout.root(
      rx.callout.icon(rx.icon(tag="info")),
      rx.callout.text("You will need admin privileges to install and access this application."),
      **props
  )
---

```python exec
import reflex as rx
```

# Callout

A `callout` is a short message to attract user's attention.

```python demo
rx.callout(
    "You will need admin privileges to install and access this application.",
    icon="info",
)
```

```python test
def test_callout_shows_icon_and_text(demo):
    expect(demo.locator(".rt-CalloutText")).to_have_text(
        "You will need admin privileges to install and access this application."
    )
    expect(demo.locator(".rt-CalloutIcon svg.lucide-info")).to_be_visible()
```

The `icon` prop allows an icon to be passed to the `callout` component. See the [**icon** component for all icons that are available.](/docs/library/data-display/icon/)

## As alert

```python demo
rx.callout(
    "Access denied. Please contact the network administrator to view this page.",
    icon="triangle_alert",
    color_scheme="red",
    role="alert",
)
```

```python test
def test_callout_as_alert(demo):
    alert = demo.get_by_role("alert")
    expect(alert).to_have_text(
        "Access denied. Please contact the network administrator to view this page."
    )
    expect(alert).to_have_attribute("data-accent-color", "red")
    expect(alert.locator(".rt-CalloutIcon svg.lucide-triangle-alert")).to_be_visible()
```

## Style

### Size

Use the `size` prop to control the size.

```python demo
rx.flex(
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        size="3",
    ),
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        size="2",
    ),
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        size="1",
    ),
    direction="column",
    spacing="3",
    align="start",
)
```

```python test
def test_callout_sizes(demo):
    callouts = demo.locator(".rt-CalloutRoot")
    expect(callouts).to_have_count(3)
    for i, size in enumerate(["3", "2", "1"]):
        expect(callouts.nth(i)).to_have_class(re.compile(rf"\brt-r-size-{size}\b"))
        expect(callouts.nth(i)).to_have_text(
            "You will need admin privileges to install and access this application."
        )
```

### Variant

Use the `variant` prop to control the visual style. It is set to `soft` by default.

```python demo
rx.flex(
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        variant="soft",
    ),
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        variant="surface",
    ),
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        variant="outline",
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_callout_variants(demo):
    callouts = demo.locator(".rt-CalloutRoot")
    expect(callouts).to_have_count(3)
    for i, variant in enumerate(["soft", "surface", "outline"]):
        expect(callouts.nth(i)).to_have_class(re.compile(rf"\brt-variant-{variant}\b"))
        expect(callouts.nth(i)).to_have_text(
            "You will need admin privileges to install and access this application."
        )
```

### Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        color_scheme="blue",
    ),
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        color_scheme="green",
    ),
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        color_scheme="red",
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_callout_colors(demo):
    callouts = demo.locator(".rt-CalloutRoot")
    expect(callouts).to_have_count(3)
    for i, color in enumerate(["blue", "green", "red"]):
        expect(callouts.nth(i)).to_have_attribute("data-accent-color", color)
        expect(callouts.nth(i)).to_have_text(
            "You will need admin privileges to install and access this application."
        )
```

### High Contrast

Use the `high_contrast` prop to add additional contrast.

```python demo
rx.flex(
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
    ),
    rx.callout(
        "You will need admin privileges to install and access this application.",
        icon="info",
        high_contrast=True,
    ),
    direction="column",
    spacing="3",
)
```

```python test
def test_callout_high_contrast(demo):
    expect(demo.locator(".rt-CalloutRoot")).to_have_text(
        ["You will need admin privileges to install and access this application."] * 2
    )
    expect(demo.locator(".rt-CalloutRoot.rt-high-contrast")).to_have_count(1)
```
