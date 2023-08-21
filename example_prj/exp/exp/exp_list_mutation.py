import reflex as rx

class State(rx.State):
    convo: list[dict[str, str]] = []
    prompt: str = ""

    def reset(self):
        # breakpoint()
        self.convo = []
        # self.convo = rx.vars.ReflexList([], reassign_field=self._reassign_field, field_name="convo")


    def claude(self):
        self.convo.append({"role": "user", "content": self.prompt})
        self.convo.append({"role": "assistant", "content": ""})
        self.convo.append({"role": "assistant", "content": "a content here"})
        self.convo.append({"role": "assistant", "content": "another content"})


def index():
    return rx.center(
        rx.vstack(
            rx.text("Okay here there, I am here"),
            rx.text(State.convo.to_string()),
            rx.foreach(
                State.convo,
                lambda message: rx.responsive_grid(
                    rx.cond(
                        message["role"] == "assistant",
                        rx.box(
                            rx.markdown(
                                message["content"],
                            ),
                            bg="#D7D7D7",
                            padding="1.0em",
                            width="100%",
                            border_radius="lg",
                        ),
                    ),
                    rx.cond(
                        message["role"] == "user",
                        rx.box(
                            rx.markdown(
                                message["content"],
                            ),
                            bg="white",
                            padding="1.0em",
                            width="100%",
                            border_radius="lg",
                        ),
                    ),
                    columns=[1],
                    width="100%",
                    spacing="1.0em",
                ),
            ),
            rx.button(
                "submit",
                on_click= State.claude
            ),
            rx.button(
                "Reset Chat",
                on_click=State.reset,
            ),
        ),
    )


app = rx.App()
app.add_page(index)
app.compile()