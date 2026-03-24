---
components:
    - rx.spinner
---

# Spinner

Spinner is used to display an animated loading indicator when a task is in progress.

```python exec
import reflex as rx
```

```python demo
rx.spinner()
```

## Basic Examples

Spinner can have different sizes.

```python demo
rx.vstack(
    rx.hstack(
        rx.spinner(size="1"),
        rx.spinner(size="2"),
        rx.spinner(size="3"),
        align="center",
        gap="1em"
    )
)
```

## Demo with buttons

Buttons have their own loading prop that automatically composes a spinner.

```python demo
rx.button("Bookmark", loading=True)
```

## Spinner inside a button

If you have an icon inside the button, you can use the button's disabled state and wrap the icon in a standalone rx.spinner to achieve a more sophisticated design.

```python demo
rx.button(
    rx.spinner(
        loading=True
    ),
    "Bookmark",
    disabled=True
)
```


