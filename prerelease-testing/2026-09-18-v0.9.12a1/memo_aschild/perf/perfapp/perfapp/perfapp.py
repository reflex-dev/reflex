"""~500-component page used to time the Python compile step."""

import reflex as rx

N = 500


class S(rx.State):
    """Perf state."""

    n: int = 0

    @rx.event
    def bump(self):
        self.n += 1

    @rx.event
    def bump_by(self, i: int):
        self.n += i


def index() -> rx.Component:
    """Big page.

    Returns:
        The page.
    """
    return rx.vstack(
        rx.text(S.n.to_string(), id="out"),
        *[
            rx.hstack(
                rx.button(f"b{i}", on_click=S.bump, id=f"b_{i}", size="1"),
                rx.button(f"a{i}", on_click=S.bump_by(i), id=f"a_{i}", size="1"),
                rx.text(f"row {i}"),
                rx.badge(S.n.to_string()),
            )
            for i in range(N // 4)
        ],
    )


app = rx.App()
app.add_page(index, route="/")
