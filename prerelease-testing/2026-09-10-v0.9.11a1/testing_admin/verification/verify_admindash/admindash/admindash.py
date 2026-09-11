"""Minimal AdminDash app for verification of the #7019 changelog claim."""

import reflex as rx

assert "/envs/verify2_testing_admin_0/" in rx.__file__ or "/envs/" in rx.__file__, rx.__file__


class Widget(rx.Model, table=True):
    """A widget row surfaced in the admin dashboard."""

    name: str
    qty: int
    note: str = ""


class WidgetState(rx.State):
    """App-side state that writes rows through rx.session."""

    rows: list[str] = []

    @rx.event
    def load(self):
        with rx.session() as s:
            self.rows = [f"{w.id}:{w.name}:{w.qty}" for w in s.exec(Widget.select()).all()]

    @rx.event
    def add(self):
        with rx.session() as s:
            s.add(Widget(name=f"w{len(self.rows) + 1}", qty=len(self.rows) + 1, note="n"))
            s.commit()
        return WidgetState.load


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("admindash verify"),
        rx.button("add", id="add", on_click=WidgetState.add),
        rx.text(WidgetState.rows.to_string(), id="rows"),
        rx.link("admin", href="/admin/", id="adminlink"),
        on_mount=WidgetState.load,
    )


app = rx.App(admin_dash=rx.AdminDash(models=[Widget]))
app.add_page(index)
