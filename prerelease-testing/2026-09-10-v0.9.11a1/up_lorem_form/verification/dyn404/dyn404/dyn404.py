"""Minimal repro: prod HTTP status for dynamic vs static routes."""

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("REFLEX_UNDER_TEST:", rx.__file__, rx.constants.Reflex.VERSION)


class S(rx.State):
    @rx.var
    def cur_path(self) -> str:
        return self.router.url.path


def index():
    return rx.box(rx.heading("index"), rx.text("home", id="marker"))


def static_page():
    return rx.box(rx.heading("static"), rx.text("staticpage", id="marker"))


def item(item_id: str = ""):
    return rx.box(
        rx.heading("item"),
        rx.text("item-page", id="marker"),
        rx.text(S.cur_path, id="path"),
    )


def splat():
    return rx.box(rx.heading("splat"), rx.text("splat-page", id="marker"))


app = rx.App()
app.add_page(index, route="/")
app.add_page(static_page, route="/static-page")
app.add_page(item, route="/item/[item_id]")
app.add_page(splat, route="/posts/[[...splat]]")
