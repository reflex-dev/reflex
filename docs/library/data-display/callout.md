---
components:
    - rx.callout
    - rx.callout.root
    - rx.callout.icon
    - rx.callout.text

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
from pcweb.pages import docs
```

# Callout

A `callout` is a short message to attract user's attention.

```python demo
rx.callout("You will need admin privileges to install and access this application.", icon="info")
```

The `icon` prop allows an icon to be passed to the `callout` component. See the [**icon** component for all icons that are available.](/docs/library/data-display/icon)

## As alert

```python demo
rx.callout("Access denied. Please contact the network administrator to view this page.", icon="triangle_alert", color_scheme="red", role="alert")
```

## Style

### Size

Use the `size` prop to control the size.

```python demo
rx.flex(
    rx.callout("You will need admin privileges to install and access this application.", icon="info", size="3",),
    rx.callout("You will need admin privileges to install and access this application.", icon="info", size="2",),
    rx.callout("You will need admin privileges to install and access this application.", icon="info", size="1",),
    direction="column",
    spacing="3",
    align="start",
)
```

### Variant

Use the `variant` prop to control the visual style. It is set to `soft` by default.

```python demo
rx.flex(
    rx.callout("You will need admin privileges to install and access this application.", icon="info", variant="soft",),
    rx.callout("You will need admin privileges to install and access this application.", icon="info", variant="surface",),
    rx.callout("You will need admin privileges to install and access this application.", icon="info", variant="outline",),
    direction="column",
    spacing="3",
)
```

### Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.callout("You will need admin privileges to install and access this application.", icon="info", color_scheme="blue",),
    rx.callout("You will need admin privileges to install and access this application.", icon="info", color_scheme="green",),
    rx.callout("You will need admin privileges to install and access this application.", icon="info", color_scheme="red",),
    direction="column",
    spacing="3",
)
```

### High Contrast

Use the `high_contrast` prop to add additional contrast.

```python demo
rx.flex(
    rx.callout("You will need admin privileges to install and access this application.", icon="info",),
    rx.callout("You will need admin privileges to install and access this application.", icon="info", high_contrast=True,),
    direction="column",
    spacing="3",
)
```
