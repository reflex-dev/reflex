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
    rx.callout.text("You will need admin privileges to install and access this application."),
)
```

The `callout` component is made up of a `callout.root`, which groups `callout.icon` and `callout.text` parts. This component is based on the `div` element and supports common margin props.

The `callout.icon` provides width and height for the `icon` associated with the `callout`. This component is based on the `div` element. See the [**icon** component for all icons that are available.](/docs/library/data-display/icon/)

The `callout.text` renders the callout text. This component is based on the `p` element.

## As alert

```python demo
rx.callout.root(
    rx.callout.icon(rx.icon(tag="triangle_alert")),
    rx.callout.text("Access denied. Please contact the network administrator to view this page."),
    color_scheme="red",
    role="alert",
)
```

## Style

### Size

Use the `size` prop to control the size.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        size="3",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        size="2",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        size="1",
    ),
    direction="column",
    spacing="3",
    align="start",
)
```

### Variant

Use the `variant` prop to control the visual style. It is set to `soft` by default.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        variant="soft",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        variant="surface",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        variant="outline",
    ),
    direction="column",
    spacing="3",
)
```

### Color

Use the `color_scheme` prop to assign a specific color, ignoring the global theme.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        color_scheme="blue",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        color_scheme="green",
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        color_scheme="red",
    ),
    direction="column",
    spacing="3",
)
```

### High Contrast

Use the `high_contrast` prop to add additional contrast.

```python demo
rx.flex(
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
    ),
    rx.callout.root(
        rx.callout.icon(rx.icon(tag="info")),
        rx.callout.text("You will need admin privileges to install and access this application."),
        high_contrast=True,
    ),
    direction="column",
    spacing="3",
)
```
