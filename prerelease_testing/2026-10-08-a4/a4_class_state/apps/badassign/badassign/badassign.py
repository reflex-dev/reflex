"""0.9.12-style import-time configuration of a state var default: `State.x = 5` at module level."""
import reflex as rx


class State(rx.State):
    count: int = 0

    @rx.event
    def bump(self):
        self.count += 1


State.count = 5  # worked silently on 0.9.12 (instances still started at 0); TypeError on 0.10.0a4


def index():
    return rx.vstack(rx.text(State.count, id="count"), rx.button("bump", on_click=State.bump, id="bump"))


app = rx.App()
app.add_page(index)
