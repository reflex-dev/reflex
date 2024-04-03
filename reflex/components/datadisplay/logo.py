from reflex.components.component import Component
import reflex as rx

class Logo(Component):

    @classmethod
    def create(cls, **props,):
        return rx.center(
        rx.link(
            rx.hstack(
                "Built with ",
                rx.image(src="https://raw.githubusercontent.com/reflex-dev/reflex-web/main/assets/Reflex.svg"),
                text_align="center",
                align="center",
                padding="1em",
            ),
            href="https://reflex.dev",
        ),
        **props,
        width="100%",
    )