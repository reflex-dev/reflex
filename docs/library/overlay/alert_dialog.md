---
components:
  - rx.alert_dialog.root
  - rx.alert_dialog.content
  - rx.alert_dialog.trigger
  - rx.alert_dialog.title
  - rx.alert_dialog.description
  - rx.alert_dialog.action
  - rx.alert_dialog.cancel

only_low_level:
  - True

AlertDialogRoot: |
  lambda **props: rx.alert_dialog.root(
      rx.alert_dialog.trigger(
          rx.button("Revoke access"),
      ),
      rx.alert_dialog.content(
          rx.alert_dialog.title("Revoke access"),
          rx.alert_dialog.description(
              "Are you sure? This application will no longer be accessible and any existing sessions will be expired.",
          ),
          rx.flex(
              rx.alert_dialog.cancel(
                  rx.button("Cancel"),
              ),
              rx.alert_dialog.action(
                  rx.button("Revoke access"),
              ),
              spacing="3",
          ),
      ),
      **props
  )

AlertDialogContent: |
  lambda **props: rx.alert_dialog.root(
      rx.alert_dialog.trigger(
          rx.button("Revoke access"),
      ),
      rx.alert_dialog.content(
          rx.alert_dialog.title("Revoke access"),
          rx.alert_dialog.description(
              "Are you sure? This application will no longer be accessible and any existing sessions will be expired.",
          ),
          rx.flex(
              rx.alert_dialog.cancel(
                  rx.button("Cancel"),
              ),
              rx.alert_dialog.action(
                  rx.button("Revoke access"),
              ),
              spacing="3",
          ),
          **props
      ),
  )
---

```python exec
import reflex as rx
```

# Alert Dialog

An alert dialog is a modal confirmation dialog that interrupts the user and expects a response.

The `alert_dialog.root` contains all the parts of the dialog.

The `alert_dialog.trigger` wraps the control that will open the dialog.

The `alert_dialog.content` contains the content of the dialog.

The `alert_dialog.title` is the title that is announced when the dialog is opened.

The `alert_dialog.description` is an optional description that is announced when the dialog is opened.

The `alert_dialog.action` wraps the control that will close the dialog. This should be distinguished visually from the `alert_dialog.cancel` control.

The `alert_dialog.cancel` wraps the control that will close the dialog. This should be distinguished visually from the `alert_dialog.action` control.

## Basic Example

```python demo
rx.alert_dialog.root(
    rx.alert_dialog.trigger(
        rx.button("Revoke access"),
    ),
    rx.alert_dialog.content(
        rx.alert_dialog.title("Revoke access"),
        rx.alert_dialog.description(
            "Are you sure? This application will no longer be accessible and any existing sessions will be expired.",
        ),
        rx.flex(
            rx.alert_dialog.cancel(
                rx.button("Cancel"),
            ),
            rx.alert_dialog.action(
                rx.button("Revoke access"),
            ),
            spacing="3",
        ),
    ),
)
```

```python test
def test_alert_dialog_opens_and_cancels(demo, page):
    demo.get_by_role("button", name="Revoke access").click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog.get_by_role("heading")).to_have_text("Revoke access")
    expect(dialog.get_by_text("Are you sure? This application")).to_be_visible()
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()
```

This example has a different color scheme and the `cancel` and `action` buttons are right aligned.

```python demo
rx.alert_dialog.root(
    rx.alert_dialog.trigger(
        rx.button("Revoke access", color_scheme="red"),
    ),
    rx.alert_dialog.content(
        rx.alert_dialog.title("Revoke access"),
        rx.alert_dialog.description(
            "Are you sure? This application will no longer be accessible and any existing sessions will be expired.",
            size="2",
        ),
        rx.flex(
            rx.alert_dialog.cancel(
                rx.button("Cancel", variant="soft", color_scheme="gray"),
            ),
            rx.alert_dialog.action(
                rx.button("Revoke access", color_scheme="red", variant="solid"),
            ),
            spacing="3",
            margin_top="16px",
            justify="end",
        ),
        style={"max_width": 450},
    ),
)
```

```python test
def test_alert_dialog_action_closes(demo, page):
    demo.get_by_role("button", name="Revoke access").click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog.get_by_role("heading")).to_have_text("Revoke access")
    dialog.get_by_role("button", name="Revoke access").click()
    expect(dialog).to_be_hidden()
```

Use the `inset` component to align content flush with the sides of the dialog.

```python demo
rx.alert_dialog.root(
    rx.alert_dialog.trigger(
        rx.button("Delete Users", color_scheme="red"),
    ),
    rx.alert_dialog.content(
        rx.alert_dialog.title("Delete Users"),
        rx.alert_dialog.description(
            "Are you sure you want to delete these users? This action is permanent and cannot be undone.",
            size="2",
        ),
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
            rx.alert_dialog.cancel(
                rx.button("Cancel", variant="soft", color_scheme="gray"),
            ),
            rx.alert_dialog.action(
                rx.button("Delete users", color_scheme="red"),
            ),
            spacing="3",
            justify="end",
        ),
        style={"max_width": 500},
    ),
)
```

```python test
def test_alert_dialog_inset_table(demo, page):
    demo.get_by_role("button", name="Delete Users").click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog.get_by_role("heading")).to_have_text("Delete Users")
    expect(dialog.get_by_role("row")).to_have_count(3)
    expect(dialog.get_by_role("rowheader")).to_have_text([
        "Danilo Rosa",
        "Zahra Ambessa",
    ])
    dialog.get_by_role("button", name="Delete users").click()
    expect(dialog).to_be_hidden()
```

## Events when the Alert Dialog opens or closes

The `on_open_change` event is called when the `open` state of the dialog changes. It is used in conjunction with the `open` prop.

```python demo exec
class AlertDialogState(rx.State):
    num_opens: int = 0
    opened: bool = False

    @rx.event
    def count_opens(self, value: bool):
        self.opened = value
        self.num_opens += 1


def alert_dialog():
    return rx.flex(
        rx.heading(
            f"Number of times alert dialog opened or closed: {AlertDialogState.num_opens}",
            as_="h2",
        ),
        rx.heading(f"Alert Dialog open: {AlertDialogState.opened}", as_="h2"),
        rx.alert_dialog.root(
            rx.alert_dialog.trigger(
                rx.button("Revoke access", color_scheme="red"),
            ),
            rx.alert_dialog.content(
                rx.alert_dialog.title("Revoke access"),
                rx.alert_dialog.description(
                    "Are you sure? This application will no longer be accessible and any existing sessions will be expired.",
                    size="2",
                ),
                rx.flex(
                    rx.alert_dialog.cancel(
                        rx.button("Cancel", variant="soft", color_scheme="gray"),
                    ),
                    rx.alert_dialog.action(
                        rx.button("Revoke access", color_scheme="red", variant="solid"),
                    ),
                    spacing="3",
                    margin_top="16px",
                    justify="end",
                ),
                style={"max_width": 450},
            ),
            on_open_change=AlertDialogState.count_opens,
        ),
        direction="column",
        spacing="3",
    )
```

```python test
def test_alert_dialog_on_open_change_counts(demo, page):
    # The open modal hides the page from the accessibility tree.
    count = demo.get_by_role("heading", include_hidden=True).first
    is_open = demo.get_by_role("heading", include_hidden=True).last
    expect(count).to_have_text("Number of times alert dialog opened or closed: 0")
    expect(is_open).to_have_text("Alert Dialog open: false")
    demo.get_by_role("button", name="Revoke access").click()
    expect(count).to_have_text("Number of times alert dialog opened or closed: 1")
    expect(is_open).to_have_text("Alert Dialog open: true")
    page.get_by_role("alertdialog").get_by_role("button", name="Cancel").click()
    expect(count).to_have_text("Number of times alert dialog opened or closed: 2")
    expect(is_open).to_have_text("Alert Dialog open: false")
```

## Controlling Alert Dialog with State

This example shows how to control whether the dialog is open or not with state. This is an easy way to show the dialog without needing to use the `rx.alert_dialog.trigger`.

`rx.alert_dialog.root` has a prop `open` that can be set to a boolean value to control whether the dialog is open or not.

We toggle this `open` prop with a button outside of the dialog and the `rx.alert_dialog.cancel` and `rx.alert_dialog.action` buttons inside the dialog.

```python demo exec
class AlertDialogState2(rx.State):
    opened: bool = False

    @rx.event
    def dialog_open(self):
        self.opened = ~self.opened


def alert_dialog2():
    return rx.box(
        rx.alert_dialog.root(
            rx.alert_dialog.content(
                rx.alert_dialog.title("Revoke access"),
                rx.alert_dialog.description(
                    "Are you sure? This application will no longer be accessible and any existing sessions will be expired.",
                ),
                rx.flex(
                    rx.alert_dialog.cancel(
                        rx.button("Cancel", on_click=AlertDialogState2.dialog_open),
                    ),
                    rx.alert_dialog.action(
                        rx.button(
                            "Revoke access", on_click=AlertDialogState2.dialog_open
                        ),
                    ),
                    spacing="3",
                ),
            ),
            open=AlertDialogState2.opened,
        ),
        rx.button("Button to Open the Dialog", on_click=AlertDialogState2.dialog_open),
    )
```

```python test
def test_alert_dialog_controlled_by_state(demo, page):
    demo.get_by_role("button", name="Button to Open the Dialog").click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog.get_by_role("heading")).to_have_text("Revoke access")
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()
    demo.get_by_role("button", name="Button to Open the Dialog").click()
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Revoke access").click()
    expect(dialog).to_be_hidden()
```

## Form Submission to a Database from an Alert Dialog

This example adds new users to a database from an alert dialog using a form.

1. It defines a User1 model with name and email fields.
2. The `add_user_to_db` method adds a new user to the database, checking for existing emails.
3. On form submission, it calls the `add_user_to_db` method.
4. The UI component has:

- A button to open an alert dialog
- An alert dialog containing a form to add a new user
- Input fields for name and email
- Submit and Cancel buttons

```python demo exec
class User1(rx.Model, table=True):
    """The user model."""

    name: str
    email: str


class State(rx.State):
    current_user: User1 = User1()

    @rx.event
    def add_user_to_db(self, form_data: dict):
        self.current_user = form_data
        ### Uncomment the code below to add your data to a database ###
        # with rx.session() as session:
        #     if session.exec(
        #         select(User1).where(user.email == self.current_user["email"])
        #     ).first():
        #         return rx.window_alert("User with this email already exists")
        #     session.add(User1(**self.current_user))
        #     session.commit()

        return rx.toast.info(
            f"User {self.current_user['name']} has been added.", position="bottom-right"
        )


def index() -> rx.Component:
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title(
                "Add New User",
            ),
            rx.alert_dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(placeholder="User Name", name="name"),
                    rx.input(placeholder="user@reflex.dev", name="email"),
                    rx.flex(
                        rx.alert_dialog.cancel(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.alert_dialog.action(
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

```python test
def test_alert_dialog_form_submits(demo, page):
    demo.get_by_role("button", name="Add User").click()
    dialog = page.get_by_role("alertdialog")
    expect(dialog.get_by_role("heading")).to_have_text("Add New User")
    dialog.get_by_placeholder("User Name").fill("Ada")
    dialog.get_by_placeholder("user@reflex.dev").fill("ada@example.com")
    dialog.get_by_role("button", name="Submit").click()
    expect(dialog).to_be_hidden()
    expect(page.get_by_text("User Ada has been added.")).to_be_visible()
```
