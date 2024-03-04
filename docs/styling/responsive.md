```python exec
import reflex as rx
```

# Responsive

Reflex apps can be made responsive to look good on mobile, tablet, and desktop.

You can pass a list of values to any style property to specify it's value on different screen sizes.

```python demo
rx.text(
    "Hello World",
    color=["orange", "red", "purple", "blue", "green"],
)
```

The text will change color based on your screen size. If you are on desktop, try changing the size of your browser window to see the color change.

The default breakpoints are shown below.

```json
"sm": '30em',
"md": '48em',
"lg": '62em',
"xl": '80em',
"2xl": '96em',
```

## Showing Components Based on Display

A common use case for responsive is to show different components based on the screen size.

Reflex provides useful helper components for this.

```python demo
rx.vstack(
    rx.desktop_only(
        rx.text("Desktop View"),
    ),
    rx.tablet_only(
        rx.text("Tablet View"),
    ),
    rx.mobile_only(
        rx.text("Mobile View"),
    ),
    rx.mobile_and_tablet(
        rx.text("Visible on Mobile and Tablet"),
    ),
    rx.tablet_and_desktop(
        rx.text("Visible on Desktop and Tablet"),
    ),
)
```

## Specifying Display Breakpoints

You can specify the breakpoints to use for the responsive components by using the `display` style property.

```python demo
rx.vstack(
    rx.text(
        "Hello World",
        color="green",
        display=["none", "none", "none", "none", "flex"],
    ),
    rx.text(
        "Hello World",
        color="blue",
        display=["none", "none", "none", "flex", "flex"],
    ),
    rx.text(
        "Hello World",
        color="red",
        display=["none", "none", "flex", "flex", "flex"],
    ),
    rx.text(
        "Hello World",
        color="orange",
        display=["none", "flex", "flex", "flex", "flex"],
    ),
    rx.text(
        "Hello World",
        color="yellow",
        display=["flex", "flex", "flex", "flex", "flex"],
    ),
)
```
