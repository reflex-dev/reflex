import os

import reflex as rx
import reflex.state  # noqa: F401  -- makes rx.state.<attr> resolvable

MARKED = os.environ.get("GDAPP_MARKED") == "1"


def _maybe_mark(fn):
    return rx.state._override_base_method(fn) if MARKED else fn


class Root(rx.State):
    """A state that overrides get_delta in its own class body."""

    n: int = 0
    visible: bool = False

    @rx.var(cache=False)
    def secret(self) -> str:
        return f"secret-{self.n}"

    @_maybe_mark
    def get_delta(self):
        delta = super().get_delta()
        if not self.visible:
            for inner in delta.values():
                if isinstance(inner, dict):
                    inner.pop("secret_rx_state_", None)
        return delta

    @rx.event
    def bump(self):
        self.n += 1

    @rx.event
    def show(self):
        self.visible = True


def index():
    return rx.vstack(
        rx.heading("get_delta override probe"),
        rx.text(Root.secret, id="secret"),
        rx.text(Root.n.to_string(), id="n"),
        rx.button("bump", on_click=Root.bump, id="bump"),
        rx.button("show", on_click=Root.show, id="show"),
    )


app = rx.App()
app.add_page(index, route="/")
