---
components:
  - rx.dropdown_menu.root
  - rx.dropdown_menu.content
  - rx.dropdown_menu.trigger
  - rx.dropdown_menu.item
  - rx.dropdown_menu.separator
  - rx.dropdown_menu.sub_content

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

A Dropdown Menu is composed of a `menu.root`, a `menu.trigger` and a `menu.content`. The `menu.trigger` is the element that the user interacts with to open the menu. It wraps the element that will open the dropdown menu. The `menu.content` is the component that pops out when the dropdown menu is open.

The `menu.item` contains the actual dropdown menu items and sits under the `menu.content`. The `shortcut` prop is an optional shortcut command displayed next to the item text.

The `menu.sub` contains all the parts of a submenu. There is a `menu.sub_trigger`, which is an item that opens a submenu. It must be rendered inside a `menu.sub` component. The `menu.sub_component` is the component that pops out when a submenu is open. It must also be rendered inside a `menu.sub` component.

The `menu.separator` is used to visually separate items in a dropdown menu.

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

## Events when the Dropdown Menu opens or closes

The `on_open_change` event, from the `menu.root`, is called when the `open` state of the dropdown menu changes. It is used in conjunction with the `open` prop, which is passed to the event handler.

```python demo exec
class DropdownMenuState(rx.State):
    num_opens: int = 0
    opened: bool = False

    @rx.event
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

## Opening a Dialog from Menu using State

Accessing an overlay component from within another overlay component is a common use case but does not always work exactly as expected.

The code below will not work as expected as because the dialog is within the menu and the dialog will only be open when the menu is open, rendering the dialog unusable.

```python
rx.menu.root(
    rx.menu.trigger(rx.icon("ellipsis-vertical")),
    rx.menu.content(
        rx.menu.item(
            rx.dialog.root(
            rx.dialog.trigger(rx.text("Edit")),
            rx.dialog.content(....),
            .....
            ),
        ),
    ),
)
```

In this example, we will show how to open a dialog box from a dropdown menu, where the menu will close and the dialog will open and be functional.

```python demo exec
class DropdownMenuState2(rx.State):
    which_dialog_open: str = ""

    @rx.event
    def set_which_dialog_open(self, value: str):
        self.which_dialog_open = value

    @rx.event
    def delete(self):
        yield rx.toast("Deleted item")

    @rx.event
    def save_settings(self):
        yield rx.toast("Saved settings")


def delete_dialog():
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Are you Sure?"),
            rx.alert_dialog.description(
                rx.text(
                    "This action cannot be undone. Are you sure you want to delete this item?",
                ),
                margin_bottom="20px",
            ),
            rx.hstack(
                rx.alert_dialog.action(
                    rx.button(
                        "Delete",
                        color_scheme="red",
                        on_click=DropdownMenuState2.delete,
                    ),
                ),
                rx.spacer(),
                rx.alert_dialog.cancel(rx.button("Cancel")),
            ),
        ),
        open=DropdownMenuState2.which_dialog_open == "delete",
        on_open_change=DropdownMenuState2.set_which_dialog_open(""),
    )


def settings_dialog():
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Settings"),
            rx.dialog.description(
                rx.text("Set your settings in this settings dialog."),
                margin_bottom="20px",
            ),
            rx.dialog.close(
                rx.button("Close", on_click=DropdownMenuState2.save_settings),
            ),
        ),
        open=DropdownMenuState2.which_dialog_open == "settings",
        on_open_change=DropdownMenuState2.set_which_dialog_open(""),
    )


def menu_call_dialog() -> rx.Component:
    return rx.vstack(
        rx.menu.root(
            rx.menu.trigger(rx.icon("menu")),
            rx.menu.content(
                rx.menu.item(
                    "Delete",
                    on_click=DropdownMenuState2.set_which_dialog_open("delete"),
                ),
                rx.menu.item(
                    "Settings",
                    on_click=DropdownMenuState2.set_which_dialog_open("settings"),
                ),
            ),
        ),
        rx.cond(
            DropdownMenuState2.which_dialog_open,
            rx.heading(f"{DropdownMenuState2.which_dialog_open} dialog is open"),
        ),
        delete_dialog(),
        settings_dialog(),
        align="center",
    )
```
