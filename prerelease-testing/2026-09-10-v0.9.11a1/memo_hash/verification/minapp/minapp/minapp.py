import reflex as rx


class S(rx.State):
    items: list[str] = ["a", "b", "c"]


def index():
    return rx.el.div(
        rx.foreach(
            S.items,
            lambda item, i: rx.el.div(item, id=f"row-{i}"),
        ),
    )


app = rx.App()
app.add_page(index)
