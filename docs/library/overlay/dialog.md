---
components:
    - rx.radix.dialog.root
    - rx.radix.dialog.trigger
    - rx.radix.dialog.title
    - rx.radix.dialog.content
    - rx.radix.dialog.description
    - rx.radix.dialog.close

only_low_level:
    - True

DialogRoot: |
    lambda **props: rx.dialog.root(
        rx.dialog.trigger(rx.button("Open Dialog")),
        rx.dialog.content(
            rx.dialog.title("Welcome to Reflex!"),
            rx.dialog.description(
                "This is a dialog component. You can render anything you want in here.",
            ),
            rx.dialog.close(
                rx.button("Close Dialog"),
            ),
        ),
        **props,
    )

DialogContent: |
    lambda **props: rx.dialog.root(
        rx.dialog.trigger(rx.button("Open Dialog")),
        rx.dialog.content(
            rx.dialog.title("Welcome to Reflex!"),
            rx.dialog.description(
                "This is a dialog component. You can render anything you want in here.",
            ),
            rx.dialog.close(
                rx.button("Close Dialog"),
            ),
            **props,
        ),
    )
---


```python exec
import reflex as rx
```

# Dialog

The `dialog.root` contains all the parts of a dialog.

The `dialog.trigger` wraps the control that will open the dialog.

The `dialog.content` contains the content of the dialog.

The `dialog.title` is a title that is announced when the dialog is opened.

The `dialog.description` is a description that is announced when the dialog is opened.

The `dialog.close` wraps the control that will close the dialog.

```python demo
rx.dialog.root(
    rx.dialog.trigger(rx.button("Open Dialog")),
    rx.dialog.content(
        rx.dialog.title("Welcome to Reflex!"),
        rx.dialog.description(
            "This is a dialog component. You can render anything you want in here.",
        ),
        rx.dialog.close(
            rx.button("Close Dialog", size="3"),
        ),
    ),
)
```

## In context examples

```python demo
rx.dialog.root(
    rx.dialog.trigger(
        rx.button("Edit Profile", size="4")
    ),
    rx.dialog.content(
        rx.dialog.title("Edit Profile"),
        rx.dialog.description(
            "Change your profile details and preferences.",
            size="2",
            margin_bottom="16px",
        ),
        rx.flex(
            rx.text("Name", as_="div", size="2", margin_bottom="4px", weight="bold"),
            rx.input(default_value="Freja Johnson", placeholder="Enter your name"),
            rx.text("Email", as_="div", size="2", margin_bottom="4px", weight="bold"),
            rx.input(default_value="freja@example.com", placeholder="Enter your email"),
            direction="column",
            spacing="3",
        ),
        rx.flex(
            rx.dialog.close(
                rx.button("Cancel", color_scheme="gray", variant="soft"),
            ),
            rx.dialog.close(
                rx.button("Save"),
            ),
            spacing="3",
            margin_top="16px",
            justify="end",
        ),
    ),
)
```

```python demo
rx.dialog.root(
    rx.dialog.trigger(rx.button("View users", size="4")),
    rx.dialog.content(
        rx.dialog.title("Users"),
        rx.dialog.description("The following users have access to this project."),

        rx.inset(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Full Name"),
                        rx.table.column_header_cell("Email"),
                        rx.table.column_header_cell("Group"),
                    ),
                ),
                rx.table.body(
                    rx.table.row(
                        rx.table.row_header_cell("Danilo Rosa"),
                        rx.table.cell("danilo@example.com"),
                        rx.table.cell("Developer"),
                    ),
                    rx.table.row(
                        rx.table.row_header_cell("Zahra Ambessa"),
                        rx.table.cell("zahra@example.com"),
                        rx.table.cell("Admin"),
                    ),
                ),
            ),
            side="x",
            margin_top="24px",
            margin_bottom="24px",
        ),
        rx.flex(
            rx.dialog.close(
                rx.button("Close", variant="soft", color_scheme="gray"),
            ),
            spacing="3",
            justify="end",
        ),
    ),
)
```

## Events when the Dialog opens or closes

The `on_open_change` event is called when the `open` state of the dialog changes. It is used in conjunction with the `open` prop, which is passed to the event handler.

```python demo exec
class DialogState(rx.State):
    num_opens: int = 0
    opened: bool = False

    def count_opens(self, value: bool):
        self.opened = value
        self.num_opens += 1


def dialog_example():
    return rx.flex(
        rx.heading(f"Number of times dialog opened or closed: {DialogState.num_opens}"),
        rx.heading(f"Dialog open: {DialogState.opened}"),
        rx.dialog.root(
            rx.dialog.trigger(rx.button("Open Dialog")),
            rx.dialog.content(
                rx.dialog.title("Welcome to Reflex!"),
                rx.dialog.description(
                    "This is a dialog component. You can render anything you want in here.",
                ),
                rx.dialog.close(
                    rx.button("Close Dialog", size="3"),
                ),
            ),
            on_open_change=DialogState.count_opens,
        ),
        direction="column",
        spacing="3",
    )
```
