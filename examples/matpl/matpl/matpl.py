import reflex as rx
import reflex.components.radix.themes as rdxt


class State(rx.State):
    pass


def index() -> rx.Component:
    return rdxt.box(
        rx.color_mode_switch(),
        rdxt.heading("Welcome to Reflex!"),
        rdxt.text("Radix-ui/themes edition!"),
        rdxt.button("Click me!", variant="soft"),
        rdxt.button("I'm Gray 🌈!", color="gray"),
        rdxt.text_field(),
        rdxt.theme_panel(),
    )


# Add state and page to the app.
app = rx.App(theme=rdxt.theme(accent_color="grass"), overlay_component=None)
app.add_page(index)
app.compile()