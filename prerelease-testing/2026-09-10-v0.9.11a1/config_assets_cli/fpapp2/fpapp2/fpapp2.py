import reflex as rx


class State(rx.State):
    n: int = 0

    @rx.event
    def bump(self):
        self.n += 1


def index():
    return rx.vstack(
        rx.heading("fpapp2", id="title"),
        rx.text(State.n, id="n"),
        rx.button("bump", on_click=State.bump, id="bump"),
        rx.link("about", href="/about", id="about-link"),
    )


def about():
    return rx.heading("about page", id="about-title")


app = rx.App()
app.add_page(index)
app.add_page(about, route="/about")
