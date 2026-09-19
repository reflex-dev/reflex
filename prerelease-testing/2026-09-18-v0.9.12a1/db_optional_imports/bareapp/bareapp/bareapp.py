import reflex as rx


class State(rx.State):
    n: int = 0

    def bump(self):
        self.n += 1


def index():
    return rx.vstack(rx.text(State.n.to_string()), rx.button("go", on_click=State.bump))


app = rx.App()
app.add_page(index, route="/")
