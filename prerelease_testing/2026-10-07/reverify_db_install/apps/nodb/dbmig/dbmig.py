import reflex as rx


def index() -> rx.Component:
    return rx.text("no db")


app = rx.App()
app.add_page(index)
