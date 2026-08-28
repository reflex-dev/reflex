"""Typical user component code, type-checked against installed reflex stubs."""

import reflex as rx


class AppState(rx.State):
    """App state."""

    items: list[str] = []
    on: bool = False

    @rx.event
    def toggle(self, value: bool):
        """Toggle.

        Args:
            value: New value.
        """
        self.on = value

    @rx.event
    def add(self, form_data: dict):
        """Add item.

        Args:
            form_data: Submitted form data.
        """
        self.items = [*self.items, str(form_data.get("item", ""))]


def index() -> rx.Component:
    """Page.

    Returns:
        The page.
    """
    return rx.container(
        rx.vstack(
            rx.heading("hello", size="5"),
            rx.text("a", " b ", AppState.items),
            rx.cond(AppState.on, rx.badge("on"), rx.badge("off")),
            rx.foreach(AppState.items, lambda item: rx.text(item)),
            rx.checkbox("on?", checked=AppState.on, on_change=AppState.toggle),
            rx.form(
                rx.input(name="item", placeholder="item"),
                rx.button("add", type="submit"),
                on_submit=AppState.add,
            ),
            rx.box(
                rx.link("home", href="/"),
                width="100%",
                padding="1em",
                background_color=rx.color("accent", 3),
            ),
            spacing="4",
        ),
    )


app = rx.App()
app.add_page(index, route="/")
