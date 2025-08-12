import reflex as rx

from .hello import hello


class State(rx.State):
    open: bool = False
    who: str = "world"
    saved_value: str = ""

    def handle_open_change(self, open):
        if open:
            self.saved_value = self.who
        else:
            self.who = self.saved_value
        self.open = open

    def handle_submit(self, form_data):
        who = form_data.get("who")
        self.saved_value = who or "world"
        self.handle_open_change(open=False)


def popover_editor(trigger):
    return rx.popover.root(
        rx.popover.trigger(rx.box(trigger)),
        rx.popover.content(
            rx.form.root(
                rx.input(
                    placeholder="Who are you?",
                    name="who",
                    on_change=State.set_who,
                ),
                rx.popover.close(
                    rx.button(display="none"),
                ),
                on_submit=State.handle_submit,
            ),
        ),
        open=State.open,
        on_open_change=State.handle_open_change,
    )


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Local Component Example", size="9"),
            popover_editor(
                hello(
                    name=State.who,
                    id="greeting",  # React.forwardRef lets us handle refs
                    title="Click to change name. Right-click to toggle caps.",
                    on_context_menu=rx.console_log(
                        "Yes we pass events through"
                    ).prevent_default,
                    background_color=rx.color_mode_cond(
                        light="papayawhip",
                        dark="rebeccapurple",
                    ),
                ),
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
        rx.logo(),
        rx.button(
            "Scroll to Greeting",
            on_click=rx.scroll_to("greeting"),
            margin_top="150vh",
        ),
    )


app = rx.App()
app.add_page(index)
