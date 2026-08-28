import reflex as rx
class State(rx.State):
    n: int = 0
def index() -> rx.Component:
    return rx.text("hi")
app = rx.App()
app.add_page(index)
