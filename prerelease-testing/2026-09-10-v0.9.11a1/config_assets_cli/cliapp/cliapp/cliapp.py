import reflex as rx
import plotly.graph_objects as go
import reflex_components_plotly as rxp


class State(rx.State):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1

    @rx.var
    def doubled(self) -> int:
        return self.count * 2


def index():
    return rx.vstack(
        rx.heading("cliapp", id="title"),
        rx.text(f"count=", State.count, id="count"),
        rx.text(f"doubled=", State.doubled, id="doubled"),
        rx.button("inc", on_click=State.inc, id="inc"),
        rx.link("about", href="/about", id="about-link"),
        rxp.plotly(data=go.Figure(data=[go.Bar(x=[1, 2, 3], y=[1, 3, 2])]), id="fig"),
    )


def about():
    return rx.vstack(rx.heading("about", id="about-title"))


app = rx.App()
app.add_page(index)
app.add_page(about, route="/about")
