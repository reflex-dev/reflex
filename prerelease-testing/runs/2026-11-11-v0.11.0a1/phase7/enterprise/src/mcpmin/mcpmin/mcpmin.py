"""One public page and one MCP-visible handler."""

import reflex as rx

import reflex_enterprise as rxe


class S(rx.State):
    n: int = 0

    @rxe.event
    def bump(self):
        """Add one."""
        self.n += 1


def index() -> rx.Component:
    return rx.vstack(rx.text(S.n, id="n"), rx.button("bump", id="bump", on_click=S.bump))


app = rxe.App()
app.add_page(index)
