"""Minimal repro: one state var holding a python callable that returns a radix component.

No ag_grid, no @rx.memo, no bundle_library call: just a plain python function stored in a
state var, which reflex-enterprise serializes through LiteralLambdaVar.
"""

import reflex as rx

print("VERIFY reflex from:", rx.__file__, flush=True)
assert "/envs/" in rx.__file__, rx.__file__

import reflex_enterprise as rxe  # noqa: E402


def cell_renderer(params: rx.Var) -> rx.Component:
    """Return a radix component (imports @radix-ui/themes)."""
    return rx.text("cell")


class MinState(rx.State):
    """State with a counter (survives across reloads) and a callable-bearing var."""

    count: int = 0
    col_defs: list[dict] = [{"field": "name", "cell_renderer": cell_renderer}]

    loaded: str = "on_load-did-not-run"

    @rx.event
    def inc(self):
        """Increment the counter."""
        self.count += 1

    @rx.event
    def on_load(self):
        """Page on_load handler."""
        self.loaded = "on_load-ran"



def index() -> rx.Component:
    """The only page."""
    return rx.vstack(
        rx.heading("min hydrate repro HMR"),
        rx.button(MinState.count.to_string(), on_click=MinState.inc, id="btn"),
        rx.text(MinState.loaded, id="loaded"),
        rx.text(rx.cond(MinState.is_hydrated, "hydrated", "not-hydrated"), id="hyd"),
    )


app = rxe.App()
app.add_page(index, on_load=MinState.on_load)
