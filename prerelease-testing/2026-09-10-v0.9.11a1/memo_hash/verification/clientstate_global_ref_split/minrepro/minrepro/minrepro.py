"""Minimal repro: ClientStateVar(global_ref=False) reader/writer split by a memo boundary."""

import reflex as rx

# Case A: non-global client state, reader inside an @rx.memo, writer outside it.
csa = rx._x.client_state("cs_a", default="a0", global_ref=False)
# Case B: non-global, reader and writer both plain (no memo anywhere).
csb = rx._x.client_state("cs_b", default="b0", global_ref=False)
# Case C: same as A but the ClientStateVar is explicitly included in the parent
# (the usage the create() docstring prescribes).
csc = rx._x.client_state("cs_c", default="c0", global_ref=False)
# Case D: same shape as A but global_ref=True (default).
csd = rx._x.client_state("cs_d", default="d0")
# Case E: non-global, reader and writer BOTH inside the same @rx.memo.
cse = rx._x.client_state("cs_e", default="e0", global_ref=False)
# Case F: non-global, one element that BOTH reads (value=) and writes (on_change=).
csf = rx._x.client_state("cs_f", default="", global_ref=False)
# Case G: non-global, input writes, sibling span reads (the classic "echo what you type").
csg = rx._x.client_state("cs_g", default="", global_ref=False)


@rx.memo
def card(value: str, tid: str) -> rx.Component:
    """Memo whose prop is bound to a ClientStateVar at the call site.

    Args:
        value: The client-state value.
        tid: The DOM id.

    Returns:
        The component.
    """
    return rx.el.span(value, id=tid, class_name="card")


@rx.memo
def card_and_button(tid: str, bid: str) -> rx.Component:
    """Memo that both reads and writes cse.

    Args:
        tid: The output DOM id.
        bid: The button DOM id.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(cse.value, id=tid),
        rx.el.button("set-e", on_click=cse.set_value("e-clicked"), id=bid),
    )


def page_a() -> rx.Component:
    """Case A page.

    Returns:
        The page.
    """
    return rx.el.div(
        rx.el.h1("A", id="title"),
        card(value=csa.value, tid="a-out"),
        rx.el.button("set-a", on_click=csa.set_value("a-clicked"), id="a-btn"),
        id="a-page",
    )


def page_b() -> rx.Component:
    """Case B page.

    Returns:
        The page.
    """
    return rx.el.div(
        rx.el.h1("B", id="title"),
        rx.el.span(csb.value, id="b-out"),
        rx.el.button("set-b", on_click=csb.set_value("b-clicked"), id="b-btn"),
        id="b-page",
    )


def page_c() -> rx.Component:
    """Case C page: cs included in the common parent, per the docstring.

    Returns:
        The page.
    """
    return rx.el.div(
        csc,
        rx.el.h1("C", id="title"),
        card(value=csc.value, tid="c-out"),
        rx.el.button("set-c", on_click=csc.set_value("c-clicked"), id="c-btn"),
        id="c-page",
    )


def page_d() -> rx.Component:
    """Case D page: global_ref=True.

    Returns:
        The page.
    """
    return rx.el.div(
        rx.el.h1("D", id="title"),
        card(value=csd.value, tid="d-out"),
        rx.el.button("set-d", on_click=csd.set_value("d-clicked"), id="d-btn"),
        id="d-page",
    )


def page_e() -> rx.Component:
    """Case E page: reader and writer inside the same memo.

    Returns:
        The page.
    """
    return rx.el.div(
        rx.el.h1("E", id="title"),
        card_and_button(tid="e-out", bid="e-btn"),
        id="e-page",
    )


def page_f() -> rx.Component:
    """Case F page: a single element both reads and writes.

    Returns:
        The page.
    """
    return rx.el.div(
        rx.el.h1("F", id="title"),
        rx.el.input(value=csf.value, on_change=csf.set_value, id="f-in"),
        id="f-page",
    )


def page_g() -> rx.Component:
    """Case G page: input writes, sibling span reads.

    Returns:
        The page.
    """
    return rx.el.div(
        rx.el.h1("G", id="title"),
        rx.el.input(on_change=csg.set_value, id="g-in"),
        rx.el.span(csg.value, id="g-out"),
        id="g-page",
    )


app = rx.App()
app.add_page(page_a, route="/a")
app.add_page(page_b, route="/b")
app.add_page(page_c, route="/c")
app.add_page(page_d, route="/d")
app.add_page(page_e, route="/e")
app.add_page(page_f, route="/f")
app.add_page(page_g, route="/g")
