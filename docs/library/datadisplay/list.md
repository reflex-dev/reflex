---
components:
    - rx.radix.themes.list_item
    - rx.radix.themes.ordered_list
    - rx.radix.themes.unordered_list
---

```python exec
import reflex as rx
```

# List

A `list` is a component that is used to display a list of items, stacked vertically by default. A `list` which can be either `ordered` or `unordered`. It is based on the `flex` component and therefore inherits all of its props.

An `unordered_list` has bullet points to display the list items. The `list_item` component

```python demo
rx.unordered_list(
    rx.list_item("Example 1"),
    rx.list_item("Example 2"),
    rx.list_item("Example 3"),
)
```

An `ordered_list` has numbers to display the list items.

```python demo
rx.ordered_list(
    rx.list_item("Example 1"),
    rx.list_item("Example 2"),
    rx.list_item("Example 3"),
)
```

An `unordered_list` or an `ordered_list` can have no bullet points or numbers by setting the `list_style_type` prop to `none`.

```python demo
rx.unordered_list(
    rx.list_item("Example 1"),
    rx.list_item("Example 2"),
    rx.list_item("Example 3"),
    list_style_type="none",
)
```

Lists can also be used with icons.

```python demo
rx.unordered_list(
    rx.list_item(
        rx.icon("check_circle", color="green", style={"display": "inline"}), "Allowed",
    ),
    rx.list_item(
        rx.icon("x-octagon", color="red", style={"display": "inline"}), "Not",
    ),
    rx.list_item(
        rx.icon("settings", color="grey", style={"display": "inline"}), "Settings"
    ),
    list_style_type="none",
)
```
