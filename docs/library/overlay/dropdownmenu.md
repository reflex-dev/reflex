---
components:
    - rx.radix.dropdown_menu.root
    - rx.radix.dropdown_menu.content
    - rx.radix.dropdown_menu.trigger
    - rx.radix.dropdown_menu.item
    - rx.radix.dropdown_menu.separator
    - rx.radix.dropdown_menu.sub_content

only_low_level:
    - True

DropdownMenuRoot: |
    lambda **props: rx.menu.root(
        rx.menu.trigger(rx.button("drop down menu")),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E"),
            rx.menu.item("Share"),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            rx.menu.sub(
                rx.menu.sub_trigger("More"),
                rx.menu.sub_content(
                    rx.menu.item("Eradicate"),
                    rx.menu.item("Duplicate"),
                    rx.menu.item("Archive"),
                ),
            ),
        ),
        **props
    )

DropdownMenuContent: |
    lambda **props: rx.menu.root(
        rx.menu.trigger(rx.button("drop down menu")),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E"),
            rx.menu.item("Share"),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            rx.menu.sub(
                rx.menu.sub_trigger("More"),
                rx.menu.sub_content(
                    rx.menu.item("Eradicate"),
                    rx.menu.item("Duplicate"),
                    rx.menu.item("Archive"),
                ),
            ),
            **props,
        ),
    )

DropdownMenuItem: |
    lambda **props: rx.menu.root(
        rx.menu.trigger(rx.button("drop down menu")),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E", **props),
            rx.menu.item("Share", **props),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red", **props),
            rx.menu.sub(
                rx.menu.sub_trigger("More"),
                rx.menu.sub_content(
                    rx.menu.item("Eradicate", **props),
                    rx.menu.item("Duplicate", **props),
                    rx.menu.item("Archive", **props),
                ),
            ),
        ),
    )

DropdownMenuSub: |
    lambda **props: rx.menu.root(
        rx.menu.trigger(rx.button("drop down menu")),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E"),
            rx.menu.item("Share"),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            rx.menu.sub(
                rx.menu.sub_trigger("More"),
                rx.menu.sub_content(
                    rx.menu.item("Eradicate"),
                    rx.menu.item("Duplicate"),
                    rx.menu.item("Archive"),
                ),
                **props,
            ),
        ),
    )

DropdownMenuSubTrigger: |
    lambda **props: rx.menu.root(
        rx.menu.trigger(rx.button("drop down menu")),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E"),
            rx.menu.item("Share"),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            rx.menu.sub(
                rx.menu.sub_trigger("More", **props),
                rx.menu.sub_content(
                    rx.menu.item("Eradicate"),
                    rx.menu.item("Duplicate"),
                    rx.menu.item("Archive"),
                ),
            ),
        ),
    )

DropdownMenuSubContent: |
    lambda **props: rx.menu.root(
        rx.menu.trigger(rx.button("drop down menu")),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E"),
            rx.menu.item("Share"),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            rx.menu.sub(
                rx.menu.sub_trigger("More"),
                rx.menu.sub_content(
                    rx.menu.item("Eradicate"),
                    rx.menu.item("Duplicate"),
                    rx.menu.item("Archive"),
                    **props,
                ),
            ),
        ),
    )
---



```python exec
import reflex as rx
```

# Dropdown Menu

A Dropdown Menu is a menu that offers a list of options that a user can select from. They are typically positioned near a button that will control their appearance and disappearance.

A Dropdown Menu is composed of a `dropdown_menu.root`, a `dropdown_menu.trigger` and a `dropdown_menu.content`. The `dropdown_menu.trigger` is the element that the user interacts with to open the menu. It wraps the element that will open the dropdown menu. The `dropdown_menu.content` is the component that pops out when the dropdown menu is open.

The `dropdown_menu.item` contains the actual dropdown menu items and sits under the `dropdown_menu.content`. The `shortcut` prop is an optional shortcut command displayed next to the item text.

The `dropdown_menu.sub` contains all the parts of a submenu. There is a `dropdown_menu.sub_trigger`, which is an item that opens a submenu. It must be rendered inside a `dropdown_menu.sub` component. The `dropdown_menu.sub_component` is the component that pops out when a submenu is open. It must also be rendered inside a `dropdown_menu.sub` component.

The `dropdown_menu.separator` is used to visually separate items in a dropdown menu.

```python demo
rx.menu.root(
    rx.menu.trigger(
        rx.button("Options", variant="soft"),
    ),
    rx.menu.content(
        rx.menu.item("Edit", shortcut="⌘ E"),
        rx.menu.item("Duplicate", shortcut="⌘ D"),
        rx.menu.separator(),
        rx.menu.item("Archive", shortcut="⌘ N"),
        rx.menu.sub(
            rx.menu.sub_trigger("More"),
            rx.menu.sub_content(
                rx.menu.item("Move to project…"),
                rx.menu.item("Move to folder…"),
                rx.menu.separator(),
                rx.menu.item("Advanced options…"),
            ),
        ),
        rx.menu.separator(),
        rx.menu.item("Share"),
        rx.menu.item("Add to favorites"),
        rx.menu.separator(),
        rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
    ),
)
```

# Size

```python demo
rx.flex(
    rx.menu.root(
        rx.menu.trigger(
            rx.button("Options", variant="soft", size="2"),
        ),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E"),
            rx.menu.item("Duplicate", shortcut="⌘ D"),
            rx.menu.separator(),
            rx.menu.item("Archive", shortcut="⌘ N"),
            rx.menu.separator(),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            size="2",
        ),
    ),
    rx.menu.root(
        rx.menu.trigger(
            rx.button("Options", variant="soft", size="1"),
        ),
        rx.menu.content(
            rx.menu.item("Edit", shortcut="⌘ E"),
            rx.menu.item("Duplicate", shortcut="⌘ D"),
            rx.menu.separator(),
            rx.menu.item("Archive", shortcut="⌘ N"),
            rx.menu.separator(),
            rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            size="1",
        ),
    ),
    spacing="3", 
    align="center",
)
```

## Events when the Dropdown Menu opens or closes

The `on_open_change` event, from the `dropdown_menu.root`, is called when the `open` state of the dropdown menu changes. It is used in conjunction with the `open` prop, which is passed to the event handler.

```python demo exec
class DropdownMenuState(rx.State):
    num_opens: int = 0
    opened: bool = False

    def count_opens(self, value: bool):
        self.opened = value
        self.num_opens += 1


def dropdown_menu_example():
    return rx.flex(
        rx.heading(f"Number of times Dropdown Menu opened or closed: {DropdownMenuState.num_opens}"),
        rx.heading(f"Dropdown Menu open: {DropdownMenuState.opened}"),
        rx.menu.root(
            rx.menu.trigger(
                rx.button("Options", variant="soft", size="2"),
            ),
            rx.menu.content(
                rx.menu.item("Edit", shortcut="⌘ E"),
                rx.menu.item("Duplicate", shortcut="⌘ D"),
                rx.menu.separator(),
                rx.menu.item("Archive", shortcut="⌘ N"),
                rx.menu.separator(),
                rx.menu.item("Delete", shortcut="⌘ ⌫", color="red"),
            ),
            on_open_change=DropdownMenuState.count_opens,
        ),
        direction="column",
        spacing="3",
    )
```
