"""Minimal repro: a hook-bearing component used directly inside rx.foreach.

`rxe.dnd.draggable` emits a `useDrag` hook. Inside `rx.foreach` the hook is
hoisted out of the generated `.map()` closure but still references the loop
variable, so the page compiles cleanly and then throws
`ReferenceError: <loopvar>_rx_state_ is not defined` in the browser.
The supported spelling is to wrap the body in `@rx.memo` (see /memo).
"""

import reflex as rx

import reflex_enterprise as rxe


@rx.memo
def memo_chip(iid: rx.Var[str]) -> rx.Component:
    """Same draggable, wrapped in @rx.memo."""
    return rxe.dnd.draggable(rx.text(iid), type="X", item={"id": iid})


@rx.page(route="/", title="foreach hook")
def index() -> rx.Component:
    return rx.vstack(
        rx.text("raw foreach", id="hdr"),
        rx.foreach(
            rx.Var.create(["a", "b"]),
            lambda iid: rxe.dnd.draggable(rx.text(iid), type="X", item={"id": iid}),
        ),
        id="raw",
    )


@rx.page(route="/memo", title="foreach hook memo")
def memo_page() -> rx.Component:
    return rx.vstack(
        rx.text("memo foreach", id="hdr"),
        rx.foreach(rx.Var.create(["a", "b"]), lambda iid: memo_chip(iid=iid)),
        id="memo",
    )


app = rxe.App()
