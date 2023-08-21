from rxconfig import config
import reflex as rx


# Backend state
class State(rx.State):
    """The app state."""
    boxes_names = ["CB1", "CB2", "CB3"]
    checked: dict = {}

    def check_box(self, index, value):
        self.checked[index] = value
        yield State.get_data()

    def get_data(self):
        pass  # do some logic that get data

    def clear_checkboxes(self):
        # Once either of the following two lines run, the checkboxes will not update on the frontend without refreshing the browser
        self.checked = {}
        print(f"checked: {self.checked}")
        print(f"State.checked: {State.checked}")
        # yield self.reset()


# Frontend components
def cbox(name, index):
    return rx.hstack(
        rx.text(name),
        rx.checkbox(
            is_checked=rx.cond(State.checked[index], True, False),
            on_change=lambda v: State.check_box(index, v)
        ),
    )


# Frontend
def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.vstack(
                rx.foreach(State.boxes_names, cbox)
            ),
            rx.button(
                "Clear Checkboxes",
                on_click=State.clear_checkboxes,
            ),
            spacing="2em",

        ),
        rx.divider(),
        rx.text(State.checked.to_string())
    )


# Add state and page to the app.
app = rx.App(state=State)
app.add_page(index)
app.compile()
