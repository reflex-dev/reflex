---
components:
    - rx.radix.checkbox

HighLevelCheckbox: |
    lambda **props: rx.radix.themes.checkbox("Basic Checkbox", **props)
---

```python exec
import reflex as rx
```

# Checkbox

Checkboxes allow users to select one or more items from a set.

## Basic example

```python demo
rx.checkbox()
```

The `checkbox` component takes a `text` prop, which is the text label associated with the checkbox.

The `default_checked` prop defines whether the `checkbox` is checked by default.

The `gap` prop determines the space between the `checkbox` and the `text` label.

```python demo
rx.checkbox("Agree to Terms and Conditios", default_checked=True, spacing="2")

```

The `size` prop determines the size of the `checkbox` and the associated `text` label.

```python demo
rx.checkbox("Agree to Terms and Conditios", size="3")
```

### Disabled

The `disabled` prop disables the `checkbox`, by default it is `False`. A disabled `checkbox` does not respond to user interactions such as click and cannot be focused.

```python demo
rx.hstack(
    rx.checkbox(),
    rx.checkbox(disabled=True),
)
```

## Triggers

### OnChange

The `on_change` trigger is called when the `checkbox` is clicked.

```python demo
rx.checkbox("Agree to Terms and Conditios", default_checked=True, on_change=rx.window_alert("Checked!"))
```

The `checkbox` can also take other styling props such as `color_scheme` and `variant`.

```python demo
rx.checkbox("Agree to Terms and Conditios", size="3", color_scheme="red", variant="soft")
```

## Real World Example

```python demo
rx.flex(
    rx.heading("Terms and Conditions"),
    rx.text("Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed neque elit, tristique placerat feugiat ac, facilisis vitae arcu. Proin eget egestas augue. Praesent ut  sem nec arcu 'pellentesque aliquet. Duis dapibus diam vel metus tempus vulputate.",
    ),
    rx.checkbox("I certify that I have read and agree to the terms and conditions for this reservation.", spacing="2", size="2", default_checked=True),
    rx.button("Book Reservation"),
    direction="column",
    align_items="start",
    border="1px solid #e2e8f0",
    background_color="#f7fafc",
    border_radius="15px",
    spacing="3",
    padding="1em",
)
```
