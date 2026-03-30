---
components:
  - rx.context_menu.root
  - rx.context_menu.item
  - rx.context_menu.separator
  - rx.context_menu.trigger
  - rx.context_menu.content
  - rx.context_menu.sub
  - rx.context_menu.sub_trigger
  - rx.context_menu.sub_content

only_low_level:
  - True

ContextMenuRoot: |
  lambda **props: rx.context_menu.root(
          rx.context_menu.trigger(
              rx.text("Context Menu (right click)")
          ),
          rx.context_menu.content(
              rx.context_menu.item("Copy", shortcut="⌘ C"),
              rx.context_menu.item("Share"),
              rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red"),
              rx.context_menu.sub(
                  rx.context_menu.sub_trigger("More"),
                  rx.context_menu.sub_content(
                      rx.context_menu.item("Eradicate"),
                      rx.context_menu.item("Duplicate"),
                      rx.context_menu.item("Archive"),
                  ),
              ),
          ),
          **props
      )

ContextMenuTrigger: |
  lambda **props: rx.context_menu.root(
          rx.context_menu.trigger(
              rx.text("Context Menu (right click)"),
              **props
          ),
          rx.context_menu.content(
              rx.context_menu.item("Copy", shortcut="⌘ C"),
              rx.context_menu.item("Share"),
              rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red"),
              rx.context_menu.sub(
                  rx.context_menu.sub_trigger("More"),
                  rx.context_menu.sub_content(
                      rx.context_menu.item("Eradicate"),
                      rx.context_menu.item("Duplicate"),
                      rx.context_menu.item("Archive"),
                  ),
              ),
          ),
      )

ContextMenuContent: |
  lambda **props: rx.context_menu.root(
          rx.context_menu.trigger(
              rx.text("Context Menu (right click)")
          ),
          rx.context_menu.content(
              rx.context_menu.item("Copy", shortcut="⌘ C"),
              rx.context_menu.item("Share"),
              rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red"),
              rx.context_menu.sub(
                  rx.context_menu.sub_trigger("More"),
                  rx.context_menu.sub_content(
                      rx.context_menu.item("Eradicate"),
                      rx.context_menu.item("Duplicate"),
                      rx.context_menu.item("Archive"),
                  ),
              ),
              **props
          ),
      )

ContextMenuSub: |
  lambda **props: rx.context_menu.root(
          rx.context_menu.trigger(
              rx.text("Context Menu (right click)")
          ),
          rx.context_menu.content(
              rx.context_menu.item("Copy", shortcut="⌘ C"),
              rx.context_menu.item("Share"),
              rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red"),
              rx.context_menu.sub(
                  rx.context_menu.sub_trigger("More"),
                  rx.context_menu.sub_content(
                      rx.context_menu.item("Eradicate"),
                      rx.context_menu.item("Duplicate"),
                      rx.context_menu.item("Archive"),
                  ),
              **props
              ),
          ),
      )

ContextMenuSubTrigger: |
  lambda **props: rx.context_menu.root(
          rx.context_menu.trigger(
              rx.text("Context Menu (right click)")
          ),
          rx.context_menu.content(
              rx.context_menu.item("Copy", shortcut="⌘ C"),
              rx.context_menu.item("Share"),
              rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red"),
              rx.context_menu.sub(
                  rx.context_menu.sub_trigger("More", **props),
                  rx.context_menu.sub_content(
                      rx.context_menu.item("Eradicate"),
                      rx.context_menu.item("Duplicate"),
                      rx.context_menu.item("Archive"),
                  ),
              ),
          ),
      )

ContextMenuSubContent: |
  lambda **props: rx.context_menu.root(
          rx.context_menu.trigger(
              rx.text("Context Menu (right click)")
          ),
          rx.context_menu.content(
              rx.context_menu.item("Copy", shortcut="⌘ C"),
              rx.context_menu.item("Share"),
              rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red"),
              rx.context_menu.sub(
                  rx.context_menu.sub_trigger("More"),
                  rx.context_menu.sub_content(
                      rx.context_menu.item("Eradicate"),
                      rx.context_menu.item("Duplicate"),
                      rx.context_menu.item("Archive"),
                      **props
                  ),
              ),
          ),
      )

ContextMenuItem: |
  lambda **props: rx.context_menu.root(
          rx.context_menu.trigger(
              rx.text("Context Menu (right click)")
          ),
          rx.context_menu.content(
              rx.context_menu.item("Copy", shortcut="⌘ C", **props),
              rx.context_menu.item("Share", **props),
              rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red", **props),
              rx.context_menu.sub(
                  rx.context_menu.sub_trigger("More"),
                  rx.context_menu.sub_content(
                      rx.context_menu.item("Eradicate", **props),
                      rx.context_menu.item("Duplicate", **props),
                      rx.context_menu.item("Archive", **props),
                  ),
              ),
          ),
      )
---

```python exec
import reflex as rx
```

# Context Menu

A Context Menu is a popup menu that appears upon user interaction, such as a right-click or a hover.

## Basic Usage

A Context Menu is composed of a `context_menu.root`, a `context_menu.trigger` and a `context_menu.content`. The `context_menu_root` contains all the parts of a context menu. The `context_menu.trigger` is the element that the user interacts with to open the menu. It wraps the element that will open the context menu. The `context_menu.content` is the component that pops out when the context menu is open.

The `context_menu.item` contains the actual context menu items and sits under the `context_menu.content`.

The `context_menu.sub` contains all the parts of a submenu. There is a `context_menu.sub_trigger`, which is an item that opens a submenu. It must be rendered inside a `context_menu.sub` component. The `context_menu.sub_content` is the component that pops out when a submenu is open. It must also be rendered inside a `context_menu.sub` component.

The `context_menu.separator` is used to visually separate items in a context menu.

```python demo
rx.context_menu.root(
    rx.context_menu.trigger(
       rx.button("Right click me"),
    ),
    rx.context_menu.content(
        rx.context_menu.item("Edit", shortcut="⌘ E"),
        rx.context_menu.item("Duplicate", shortcut="⌘ D"),
        rx.context_menu.separator(),
        rx.context_menu.item("Archive", shortcut="⌘ N"),
        rx.context_menu.sub(
            rx.context_menu.sub_trigger("More"),
            rx.context_menu.sub_content(
                rx.context_menu.item("Move to project…"),
                rx.context_menu.item("Move to folder…"),
                rx.context_menu.separator(),
                rx.context_menu.item("Advanced options…"),
            ),
        ),
        rx.context_menu.separator(),
        rx.context_menu.item("Share"),
        rx.context_menu.item("Add to favorites"),
        rx.context_menu.separator(),
        rx.context_menu.item("Delete", shortcut="⌘ ⌫", color="red"),
    ),
)
```

````md alert warning
# `rx.context_menu.item` must be a DIRECT child of `rx.context_menu.content`

The code below for example is not allowed:

```python
rx.context_menu.root(
    rx.context_menu.trigger(
       rx.button("Right click me"),
    ),
    rx.context_menu.content(
        rx.cond(
            State.count % 2 == 0,
            rx.vstack(
                rx.context_menu.item("Even Option 1", on_click=State.set_selected_option("Even Option 1")),
                rx.context_menu.item("Even Option 2", on_click=State.set_selected_option("Even Option 2")),
                rx.context_menu.item("Even Option 3", on_click=State.set_selected_option("Even Option 3")),
            ),
            rx.vstack(
                rx.context_menu.item("Odd Option A", on_click=State.set_selected_option("Odd Option A")),
                rx.context_menu.item("Odd Option B", on_click=State.set_selected_option("Odd Option B")),
                rx.context_menu.item("Odd Option C", on_click=State.set_selected_option("Odd Option C")),
            )
        )
    ),
)
```
````

## Opening a Dialog from Context Menu using State

Accessing an overlay component from within another overlay component is a common use case but does not always work exactly as expected.

The code below will not work as expected as because the dialog is within the menu and the dialog will only be open when the menu is open, rendering the dialog unusable.

```python
rx.context_menu.root(
    rx.context_menu.trigger(rx.icon("ellipsis-vertical")),
    rx.context_menu.content(
        rx.context_menu.item(
            rx.dialog.root(
            rx.dialog.trigger(rx.text("Edit")),
            rx.dialog.content(....),
            .....
            ),
        ),
    ),
)
```

In this example, we will show how to open a dialog box from a context menu, where the menu will close and the dialog will open and be functional.

```python demo exec
class ContextMenuState(rx.State):
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
                        on_click=ContextMenuState.delete,
                    ),
                ),
                rx.spacer(),
                rx.alert_dialog.cancel(rx.button("Cancel")),
            ),
        ),
        open=ContextMenuState.which_dialog_open == "delete",
        on_open_change=ContextMenuState.set_which_dialog_open(""),
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
                rx.button("Close", on_click=ContextMenuState.save_settings),
            ),
        ),
        open=ContextMenuState.which_dialog_open == "settings",
        on_open_change=ContextMenuState.set_which_dialog_open(""),
    )


def context_menu_call_dialog() -> rx.Component:
    return rx.vstack(
        rx.context_menu.root(
            rx.context_menu.trigger(rx.icon("ellipsis-vertical")),
            rx.context_menu.content(
                rx.context_menu.item(
                    "Delete",
                    on_click=ContextMenuState.set_which_dialog_open("delete"),
                ),
                rx.context_menu.item(
                    "Settings",
                    on_click=ContextMenuState.set_which_dialog_open("settings"),
                ),
            ),
        ),
        rx.cond(
            ContextMenuState.which_dialog_open,
            rx.heading(f"{ContextMenuState.which_dialog_open} dialog is open"),
        ),
        delete_dialog(),
        settings_dialog(),
        align="center",
    )
```
