"""Minimal core repro: does a component that consumes an UNCHANGED substate re-render after hydration?

Each probe renders `typeof __reflex` (the global that reflex sets in a useEffect of
ReflexProviders) together with a State var. If the component never re-renders after
mount, it keeps showing NO_REFLEX - this is what makes reflex-enterprise's
`formatColumnDefs` return [] (empty AG Grid columns) in prod on 0.10.
"""

import reflex as rx

PROBE = rx.vars.function.FunctionStringVar.create(
    "((v) => (typeof __reflex === 'undefined' ? 'NO_REFLEX' : 'HAS_REFLEX') + ':' + JSON.stringify(v))"
)


class Untouched(rx.State):
    """Substate whose values equal the compiled defaults (never changed by the backend)."""

    cols: list[str] = ["a", "b"]
    n: int = 0

    @rx.event
    def bump(self):
        self.n += 1


class Touched(rx.State):
    """Substate changed by on_load, so the boot hydrate must deliver it."""

    cols: list[str] = ["x"]

    @rx.event
    def load(self):
        self.cols = ["x", "y"]


def index():
    return rx.vstack(
        rx.heading("core re-render probe"),
        rx.text(PROBE.call(Untouched.cols), id="untouched"),
        rx.text(PROBE.call(Touched.cols), id="touched"),
        rx.text(PROBE.call(rx.State.is_hydrated), id="root"),
        rx.text(Untouched.n, id="n"),
        rx.button("bump other var of Untouched", on_click=Untouched.bump, id="bump"),
        rx.link("other page", href="/other", id="to-other"),
    )


def other():
    return rx.vstack(
        rx.text("other page"),
        rx.link("back", href="/", id="to-index"),
    )


app = rx.App()
app.add_page(index, on_load=Touched.load)
app.add_page(other, route="/other")
