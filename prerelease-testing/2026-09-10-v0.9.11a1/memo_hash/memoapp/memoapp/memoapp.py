"""memoapp — end-to-end exercise of #6947 auto-memoization naming and hashing."""

import reflex as rx

from . import custom_a, custom_b, mod_a, mod_b
from .common import Shared
from .props_mod import props_panel

cs = rx._x.client_state("memo_cs", default="cs0", global_ref=False)
cs_g = rx._x.client_state("memo_cs_g", default="csg0")


@rx.memo
def cs_card(value: str, tid: str) -> rx.Component:
    """A memo whose prop is bound to a ClientStateVar at the call site.

    Args:
        value: The client-state value.
        tid: The DOM id.

    Returns:
        The component.
    """
    return rx.el.span(value, id=tid, class_name="memo-cs")


@rx.memo
def counter_holder(tid: str) -> rx.Component:
    """A memo that wraps two same-named ComponentState instances.

    Args:
        tid: The DOM id.

    Returns:
        The component.
    """
    return rx.el.div(
        mod_a.CounterA.create(btn_id="held-a-btn", out_id="held-a-out"),
        mod_b.CounterB.create(btn_id="held-b-btn", out_id="held-b-out"),
        id=tid,
    )


def nav() -> rx.Component:
    """Site nav.

    Returns:
        The nav bar.
    """
    return rx.el.div(
        *[
            rx.link(name, href=href, id=f"nav-{name}", padding="0 6px")
            for name, href in (
                ("index", "/"),
                ("samename", "/samename"),
                ("custom", "/custom"),
                ("props", "/props"),
                ("foreach", "/foreach"),
                ("page2", "/page2"),
            )
        ],
        id="nav",
    )


def same_name_panel(suffix: str) -> rx.Component:
    """Both modules' same-named memo cards and ComponentStates.

    Args:
        suffix: Distinguishes DOM ids between pages.

    Returns:
        The panel.
    """
    return rx.el.div(
        rx.el.div(
            mod_a.card(label="card-A"),
            mod_b.card(label="card-B"),
            id=f"cards-{suffix}",
        ),
        rx.el.div(
            "A.clicks=",
            rx.el.span(mod_a.StateA.clicks.to_string(), id=f"a-clicks-{suffix}"),
            " B.clicks=",
            rx.el.span(mod_b.StateB.clicks.to_string(), id=f"b-clicks-{suffix}"),
            id=f"clicks-{suffix}",
        ),
        rx.el.div(
            mod_a.CounterA.create(btn_id=f"cs-a-btn-{suffix}", out_id=f"cs-a-out-{suffix}"),
            mod_b.CounterB.create(btn_id=f"cs-b-btn-{suffix}", out_id=f"cs-b-out-{suffix}"),
            id=f"counters-{suffix}",
        ),
        id=f"samename-{suffix}",
    )


def index() -> rx.Component:
    """Index page.

    Returns:
        The page.
    """
    return rx.el.div(
        nav(),
        rx.el.h1("memoapp", id="title"),
        rx.el.button("relabel", on_click=Shared.relabel, id="relabel"),
        rx.el.span(Shared.label, id="shared-label"),
        id="index-page",
    )


def samename() -> rx.Component:
    """Same-named memo / ComponentState page.

    Returns:
        The page.
    """
    return rx.el.div(nav(), same_name_panel("p1"), id="samename-page")


def custom() -> rx.Component:
    """Custom-component collision page.

    Returns:
        The page.
    """
    return rx.el.div(
        nav(),
        rx.el.div(custom_a.widgets(), id="custom-a"),
        rx.el.div(custom_b.widgets(), id="custom-b"),
        rx.el.button("relabel", on_click=Shared.relabel, id="relabel"),
        id="custom-page",
    )


def props() -> rx.Component:
    """Dataclass / enum prop page.

    Returns:
        The page.
    """
    return rx.el.div(nav(), props_panel(), id="props-page")


def foreach() -> rx.Component:
    """Foreach + ComponentState + client-state page.

    Returns:
        The page.
    """
    return rx.el.div(
        nav(),
        rx.el.div(
            rx.foreach(
                Shared.items,
                lambda item, i: rx.el.div(
                    mod_a.card(label=item),
                    mod_b.card(label=item),
                    id=f"row-{i}",
                ),
            ),
            id="foreach-rows",
        ),
        rx.el.div(
            "A.clicks=",
            rx.el.span(mod_a.StateA.clicks.to_string(), id="fe-a-clicks"),
            " B.clicks=",
            rx.el.span(mod_b.StateB.clicks.to_string(), id="fe-b-clicks"),
            id="fe-clicks",
        ),
        counter_holder(tid="held"),
        rx.el.div(
            cs_card(value=cs.value, tid="cs-out"),
            rx.el.button("set-cs", on_click=cs.set_value("cs-clicked"), id="cs-btn"),
            cs_card(value=cs_g.value, tid="csg-out"),
            rx.el.button("set-csg", on_click=cs_g.set_value("csg-clicked"), id="csg-btn"),
            id="cs-wrap",
        ),
        id="foreach-page",
    )


def page2() -> rx.Component:
    """A second page reusing the same memos (navigation test).

    Returns:
        The page.
    """
    return rx.el.div(
        nav(),
        rx.el.h2("page2", id="page2-title"),
        same_name_panel("p2"),
        rx.el.div(custom_a.widgets(), id="custom-a"),
        rx.el.div(custom_b.widgets(), id="custom-b"),
        id="page2-page",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(samename, route="/samename")
app.add_page(custom, route="/custom")
app.add_page(props, route="/props")
app.add_page(foreach, route="/foreach")
app.add_page(page2, route="/page2")
