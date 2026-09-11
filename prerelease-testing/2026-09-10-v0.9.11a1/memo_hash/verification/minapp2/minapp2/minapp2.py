import reflex as rx


class S(rx.State):
    name: str = "x"


def index():
    # No foreach, no memoization -- a single dynamic id built with an f-string.
    return rx.el.div(
        rx.el.div("hello", id=f"row-{S.name}"),
    )


app = rx.App()
app.add_page(index)
