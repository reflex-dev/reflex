import reflex as rx


class Widget(rx.Model, table=True):
    """A widget row for the admin dashboard."""

    name: str
    qty: int = 0


class State(rx.State):
    count: int = 0

    @rx.event
    def bump(self):
        self.count += 1


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("admin probe"),
        rx.text(f"count={State.count}", id="count"),
        rx.button("bump", on_click=State.bump, id="bump"),
        rx.link("admin", href="/admin/", id="adminlink"),
    )


app = rx.App(admin_dash=rx.AdminDash(models=[Widget]))
app.add_page(index, route="/")
