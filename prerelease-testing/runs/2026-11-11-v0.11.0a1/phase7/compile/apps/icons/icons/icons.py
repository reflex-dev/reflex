"""FINDING-042: lucide digit icon names through a Var tag (fixed in reflex-components-lucide 1.1.2a1)."""

import reflex as rx


class S(rx.State):
    icon_name: str = "grid_2x_2"
    names: list[str] = ["grid_2x_2", "grid_3x_3", "house", "align_center"]

    @rx.event
    def flip(self):
        self.icon_name = "grid_3x_3" if self.icon_name == "grid_2x_2" else "grid_2x_2"


def index():
    return rx.vstack(
        rx.heading("icons", id="h"),
        rx.box(rx.icon(S.icon_name), id="var-icon"),
        rx.box(rx.icon("grid_2x_2"), id="static-icon"),
        rx.foreach(S.names, lambda n: rx.box(rx.icon(n), rx.text(n), class_name="fe-icon")),
        rx.button("flip", on_click=S.flip, id="flip"),
    )


app = rx.App()
app.add_page(index)
