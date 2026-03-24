---
components:
  - rx.dialog.root
  - rx.dialog.trigger
  - rx.dialog.title
  - rx.dialog.content
  - rx.dialog.description
  - rx.dialog.close

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
from pcweb.pages.docs import library
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

    @rx.event
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

Check out the [menu docs]({library.overlay.dropdown_menu.path}) for an example of opening a dialog from within a dropdown menu.

## Form Submission to a Database from a Dialog

This example adds new users to a database from a dialog using a form.

1. It defines a User model with name and email fields.
2. The `add_user_to_db` method adds a new user to the database, checking for existing emails.
3. On form submission, it calls the `add_user_to_db` method.
4. The UI component has:

- A button to open a dialog
- A dialog containing a form to add a new user
- Input fields for name and email
- Submit and Cancel buttons

```python demo exec
class User(rx.Model, table=True):
    """The user model."""
    name: str
    email: str

class State(rx.State):

    current_user: User = User()

    @rx.event
    def add_user_to_db(self, form_data: dict):
        self.current_user = form_data
        ### Uncomment the code below to add your data to a database ###
        # with rx.session() as session:
        #     if session.exec(
        #         select(User).where(user.email == self.current_user["email"])
        #     ).first():
        #         return rx.window_alert("User with this email already exists")
        #     session.add(User(**self.current_user))
        #     session.commit()

        return rx.toast.info(f"User {self.current_user['name']} has been added.", position="bottom-right")


def index() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Add New User",
            ),
            rx.dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(
                        placeholder="User Name", name="name"
                    ),
                    rx.input(
                        placeholder="user@reflex.dev", name="email"
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button("Submit", type="submit"),
                        ),
                        spacing="3",
                        justify="end",
                    ),
                    direction="column",
                    spacing="4",
                ),
                on_submit=State.add_user_to_db,
                reset_on_submit=False,
            ),
            max_width="450px",
        ),
    )
```
