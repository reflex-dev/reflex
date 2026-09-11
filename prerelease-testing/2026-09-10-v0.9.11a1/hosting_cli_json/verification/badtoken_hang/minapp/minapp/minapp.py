import reflex as rx


def index() -> rx.Component:
    return rx.text("hello")


app = rx.App()
app.add_page(index)
