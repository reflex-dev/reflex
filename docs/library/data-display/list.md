---
components:
    - rx.list.item
    - rx.list.ordered
    - rx.list.unordered
---

```python exec
import reflex as rx
```

# List

A `list` is a component that is used to display a list of items, stacked vertically by default. A `list` can be either `ordered` or `unordered`. It is based on the `flex` component and therefore inherits all of its props.

`list.unordered` has bullet points to display the list items.

```python demo
rx.list.unordered(
    rx.list.item("Example 1"),
    rx.list.item("Example 2"),
    rx.list.item("Example 3"),
)
```

 `list.ordered` has numbers to display the list items.

```python demo
rx.list.ordered(
    rx.list.item("Example 1"),
    rx.list.item("Example 2"),
    rx.list.item("Example 3"),
)
```

`list.unordered()` and `list.ordered()` can have no bullet points or numbers by setting the `list_style_type` prop to `none`.
This is effectively the same as using the `list()` component.

```python demo
rx.hstack(
    rx.list(
        rx.list.item("Example 1"),
        rx.list.item("Example 2"),
        rx.list.item("Example 3"),
    ),
    rx.list.unordered(
        rx.list.item("Example 1"),
        rx.list.item("Example 2"),
        rx.list.item("Example 3"),
        list_style_type="none",
    )
)
```

Lists can also be used with icons.

```python demo
rx.list(
    rx.list.item(
        rx.icon("circle_check_big", color="green"), " Allowed",
    ),
    rx.list.item(
        rx.icon("octagon_x", color="red"), " Not",
    ),
    rx.list.item(
        rx.icon("settings", color="grey"), " Settings"
    ),
    list_style_type="none",
)
```
