---
components:
    - rx.chakra.Menu
    - rx.chakra.MenuButton
    - rx.chakra.MenuList
    - rx.chakra.MenuItem
    - rx.chakra.MenuDivider
    - rx.chakra.MenuGroup
    - rx.chakra.MenuOptionGroup
    - rx.chakra.MenuItemOption
---

```python exec
import reflex as rx
```

# Menu

An accessible dropdown menu for the common dropdown menu button design pattern.

```python demo
rx.chakra.menu(
    rx.chakra.menu_button("Menu"),
    rx.chakra.menu_list(
        rx.chakra.menu_item("Example"),
        rx.chakra.menu_divider(),
        rx.chakra.menu_item("Example"),
        rx.chakra.menu_item("Example"),
    ),
)
```
