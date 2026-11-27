"""The card: every variant and size, what it holds, and a card that is a link."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import ACTIVE, DARK, FOCUS_VISIBLE, HOVER, LIGHT, Matrix

VARIANTS = ["surface", "classic", "ghost"]
SIZES = ["1", "2", "3", "4", "5"]
STATES = ["rest", HOVER, FOCUS_VISIBLE, ACTIVE]
RESPONSIVE = {"responsive": rx.breakpoints(initial="1", sm="4", lg="2")}

# A translucent card blurs what is behind it, 64 pixels around: the frames
# beside its own, which are not the same for the two systems. A filter makes
# an element the root of the backdrop of what it holds.
_BACKDROP_ROOT = {"filter": "opacity(1)"}

# What shows through a translucent card.
_STRIPES = {
    "padding": "12px",
    "background_image": (
        "repeating-linear-gradient(45deg, #e5484d 0 12px, #ffc53d 12px 24px, "
        "#30a46c 24px 36px)"
    ),
}


def _words(namespace: Any) -> list[Any]:
    """Create what every card of the matrix says.

    Args:
        namespace: ``rx`` or ``rx.ui``.

    Returns:
        A heading and a paragraph.
    """
    return [
        namespace.heading("Quarterly report", size="3"),
        namespace.text(
            "Revenue grew by a fifth, and costs stayed flat.",
            size="2",
            color_scheme="gray",
        ),
    ]


def _card(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a card with real content, as the element a cell says it is.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``holds`` names what is inside the
            card, ``renders`` the element it is rendered as, ``panel`` the
            panel background of a theme around it, and ``over`` what is
            behind it.

    Returns:
        The card, or what is around it.
    """
    props = dict(props)
    holds = props.pop("holds", "actions")
    renders = props.pop("renders", None)
    panel = props.pop("panel", None)
    over = props.pop("over", None)
    props["custom_attrs"] = {"data-card": ""}
    children = _words(namespace)
    if holds == "actions" and renders is None:
        children.append(
            namespace.flex(
                namespace.button("Open", size="1"),
                namespace.button("Share", size="1", variant="soft"),
                spacing="2",
                margin_top="8px",
            )
        )
    elif holds == "inset":
        children.insert(
            0,
            namespace.inset(
                rx.el.img(
                    src=(
                        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
                        "width='40' height='20'%3E%3Crect width='40' height='20' "
                        "fill='%233e63dd'/%3E%3Ccircle cx='20' cy='10' r='6' "
                        "fill='%23ffc53d'/%3E%3C/svg%3E"
                    ),
                    alt="A sun in the sky",
                    style={"display": "block", "width": "100%", "height": "48px"},
                ),
                side="top",
                pb="current",
            ),
        )
    elif holds == "card":
        children.append(namespace.card(namespace.text("Details", size="1")))
    if renders == "link":
        card = namespace.card(
            rx.el.a(*children, href="#report"), as_child=True, **props
        )
    elif renders == "button":
        card = namespace.card(rx.el.button(*children), as_child=True, **props)
    elif renders == "label":
        card = namespace.card(rx.el.label(*children), as_child=True, **props)
    else:
        card = namespace.card(*children, **props)
    if panel is not None:
        card = namespace.theme(card, panel_background=panel)
    if over == "stripes":
        card = rx.el.div(card, style=_STRIPES)
    return rx.el.div(card, style=_BACKDROP_ROOT)


MATRIX = Matrix(
    component="card",
    render=_card,
    cross={"variant": VARIANTS, "size": SIZES},
    sweep={
        "holds": ["inset", "card"],
        "renders": ["link", "button", "label"],
        "panel": ["solid", "translucent"],
        "over": ["stripes"],
        "size": RESPONSIVE,
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {"variant": VARIANTS, "appearance": [LIGHT, DARK]},
        # A card that is a link or a button answers to the pointer and the
        # keyboard; one that is neither does not.
        {
            "variant": VARIANTS,
            "renders": ["link", "button"],
            "state": STATES,
            "appearance": [LIGHT, DARK],
        },
        {"variant": VARIANTS, "renders": ["label"], "state": ["rest", HOVER, ACTIVE]},
        {"variant": VARIANTS, "state": [HOVER, ACTIVE]},
        {"variant": VARIANTS, "holds": ["inset"], "size": ["1", "3", "5"]},
        {
            "variant": VARIANTS,
            "over": ["stripes"],
            "panel": ["solid", "translucent"],
            "appearance": [LIGHT, DARK],
        },
        {
            "size": RESPONSIVE,
            "variant": ["surface", "ghost"],
            "viewport": [520, 800, 1100, 1280],
        },
    ],
    stage=(400, 280),
    target="[data-card]",
    crop="stage",
    # No pixel may differ, at the default threshold and not at zero. At a
    # threshold of zero 117 of the 125 cells are equal, and in the others 1
    # to 12 pixels on the rounded corners of the border and of the shadow are
    # off by one or two steps of a channel, by where the frame is on the
    # page: the same props in another frame are equal (the base cell and
    # `size-responsive_variant-surface@520`, which is the same card).
    tolerance=0,
)

CONTRACT = Contract(
    component="card",
    render=lambda namespace: namespace.box(
        namespace.card(
            namespace.heading("Report", size="3"),
            namespace.text("Read by the board."),
            id="card",
        ),
        namespace.card(
            rx.el.a(namespace.text("Open the report"), href="#report"),
            as_child=True,
            id="link",
        ),
        namespace.card(
            rx.el.button(
                namespace.text("Archive"),
                on_click=rx.call_script("window.archived = (window.archived || 0) + 1"),
            ),
            as_child=True,
            id="button",
        ),
    ),
)


@CONTRACT.step(
    "is a div, or the element it is rendered as, in the server render", on=SERVER
)
def _server_render(run: Run) -> None:
    card = run.server.element("card")
    assert (card.tag, card.text) == ("div", "ReportRead by the board.")
    link = run.server.element("link")
    assert (link.tag, link.text) == ("a", "Open the report")
    assert link.attributes["href"] == f"/contract/card/{run.system.slug}/#report"
    button = run.server.element("button")
    assert (button.tag, button.text) == ("button", "Archive")


@CONTRACT.step(
    "a card that is a link navigates with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#card").is_visible()
    run.page.keyboard.press("Tab")
    assert run.page.evaluate("document.activeElement.id") == "link"
    run.page.locator("#link").click()
    assert run.page.evaluate("location.hash") == "#report"


@CONTRACT.step("has the role of the element it is rendered as", on=HYDRATED)
def _role(run: Run) -> None:
    assert run.page.locator("#card").get_attribute("role") is None
    link = run.page.get_by_role("link", name="Open the report")
    assert link.get_attribute("id") == "link"
    button = run.page.get_by_role("button", name="Archive")
    assert button.get_attribute("id") == "button"


@CONTRACT.step("Tab reaches the link and the button, not the plain card", on=HYDRATED)
def _tab(run: Run) -> None:
    focused = []
    for _ in range(2):
        run.page.keyboard.press("Tab")
        focused.append(run.page.evaluate("document.activeElement.id"))
        assert run.page.evaluate("document.activeElement.matches(':focus-visible')")
    assert focused == ["link", "button"]
    assert run.page.locator("#card").evaluate("element => element.tabIndex") == -1


@CONTRACT.step("Enter follows the link and presses the button", on=HYDRATED)
def _press(run: Run) -> None:
    run.page.locator("#link").focus()
    run.page.keyboard.press("Enter")
    run.page.wait_for_function("location.hash === '#report'")
    run.page.locator("#button").focus()
    run.page.keyboard.press("Enter")
    run.page.wait_for_function("window.archived === 1")
    run.page.keyboard.press("Space")
    run.page.wait_for_function("window.archived === 2")
    run.page.locator("#button").click()
    run.page.wait_for_function("window.archived === 3")
