"""rxe.App specifics QA app: google_font head component, badge, export."""

import reflex as rx

import reflex_enterprise as rxe


class S(rx.State):
    n: int = 0

    @rx.event
    def inc(self):
        self.n += 1


def index():
    return rx.vstack(
        rx.heading("rxe.App QA", id="h"),
        rx.text("Body text in Inter 700", weight="bold", id="t"),
        rx.text(S.n, id="n"),
        rx.button("inc", on_click=S.inc, id="inc"),
        rx.link("other", href="/other", id="to-other"),
    )


def other():
    return rx.text("other page", id="other")


app = rxe.App(
    head_components=rxe.google_font("Inter", weights=[400, 700]),
    style={"font_family": "Inter, sans-serif"},
)
app.add_page(index)
app.add_page(other, route="/other")
