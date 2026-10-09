"""Issue 1 e2e: a base state whose __init_subclass__ gives every subclass its own dynamic `loading` var.

Page1(Hooked) gets `loading` via add_var; Detail(Page1) calls add_var("loading") again for itself.
0.10 docs (#7312): a substate may declare a var named like an inherited one and gets an independent one.
"""
import reflex as rx


class Hooked(rx.State):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.add_var("loading", bool, False)


class Page1(Hooked):
    x: int = 0

    @rx.event
    def toggle(self):
        self.loading = not self.loading


class Detail(Page1):
    y: int = 0

    @rx.event
    def toggle_detail(self):
        self.loading = not self.loading


def index():
    return rx.vstack(
        rx.text(rx.cond(Page1.loading, "page1:on", "page1:off"), id="p1"),
        rx.text(rx.cond(Detail.loading, "detail:on", "detail:off"), id="det"),
        rx.button("toggle page1", on_click=Page1.toggle, id="b1"),
        rx.button("toggle detail", on_click=Detail.toggle_detail, id="b2"),
    )


app = rx.App()
app.add_page(index)
