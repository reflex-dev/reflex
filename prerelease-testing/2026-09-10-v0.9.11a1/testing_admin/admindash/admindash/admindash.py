"""Minimal AdminDash app: one rx.Model table, the admin dashboard, and a normal page."""

import reflex as rx


class Widget(rx.Model, table=True):
    """A widget row managed through the admin dashboard."""

    name: str
    qty: int = 0
    note: str = ""


class WidgetState(rx.State):
    widgets: list[Widget] = []

    @rx.event
    def load_widgets(self):
        with rx.session() as session:
            self.widgets = session.exec(Widget.select()).all()

    @rx.event
    def add_widget(self):
        with rx.session() as session:
            session.add(Widget(name=f"w{len(self.widgets) + 1}", qty=1, note="from app"))
            session.commit()
        return WidgetState.load_widgets


def index():
    return rx.vstack(
        rx.heading("widgets", id="heading"),
        rx.text(WidgetState.widgets.length().to_string(), id="nwidgets"),
        rx.button("add", on_click=WidgetState.add_widget, id="add"),
        rx.foreach(
            WidgetState.widgets,
            lambda w: rx.text(f"{w.name}:{w.qty}", class_name="w"),
        ),
        rx.link("admin", href="/admin/", id="toadmin"),
        on_mount=WidgetState.load_widgets,
    )


app = rx.App(admin_dash=rx.AdminDash(models=[Widget]))
app.add_page(index, route="/")
