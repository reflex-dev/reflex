import reflex as rx


class State(rx.State):
    cols: list[dict] = [{"title": "Name", "id": "name", "type": "str"}, {"title": "Age", "id": "age", "type": "int"}]
    data: list[list] = [["a", 1], ["b", 2]]
    icon: str = "home"

    @rx.event
    def flip(self):
        self.icon = "sun" if self.icon == "home" else "home"


def index():
    return rx.vstack(
        rx.heading("mixed graph smoke", id="h"),
        rx.icon("home", id="static-icon"),
        rx.icon(State.icon, id="dyn-icon"),
        rx.button("flip", id="flip", on_click=State.flip),
        rx.data_editor(columns=State.cols, data=State.data, id="de"),
        rx.code_block("print('x')", language="python", id="cb"),
        rx.input(id="email", name="email"),
    )


app = rx.App()
app.add_page(index)
