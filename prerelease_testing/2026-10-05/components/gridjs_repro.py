"""Minimal mutable Grid.js table to compare stable and alpha console errors."""

import reflex as rx


class State(rx.State):
    """Mutable data shared by the table and an ordinary user action."""

    data: list[list[str]] = [["Alpha", "12"], ["Beta", "9"]]

    @rx.event
    def edit(self):
        """Replace the first product after the user edits it."""
        self.data[0][0] = "Gamma"


def index() -> rx.Component:
    """Build the isolated searchable table and update action.

    Returns:
        A small table page.
    """
    return rx.vstack(
        rx.text(State.router.session.client_token, id="token"),
        rx.data_table(
            data=State.data,
            columns=["Product", "Stock"],
            pagination=True,
            search=True,
            sort=True,
        ),
        rx.button("Edit first product", on_click=State.edit),
        rx.text(State.data[0][0], id="first-product"),
    )


app = rx.App()
app.add_page(index)
