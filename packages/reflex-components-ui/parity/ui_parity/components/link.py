"""The link: its look in each state, and navigation without a page load."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, FOCUS_VISIBLE, HOVER, Matrix
from ui_parity.samples import ACCENTS


def _link(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a link, alone or inside text that changes its look.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``inside`` names the text around the
            link, and ``holds`` what the link holds beside words.

    Returns:
        The link, or the text around it.
    """
    props = dict(props)
    inside = props.pop("inside", None)
    holds = props.pop("holds", None)
    props.setdefault("href", "/docs")
    if holds == "code":
        link = namespace.link(namespace.code("rx.link"), **props)
    elif holds == "code-and-words":
        link = namespace.link("the ", namespace.code("rx.link"), " docs", **props)
    else:
        link = namespace.link("the quick brown fox", **props)
    if inside == "text":
        return namespace.text("See ", link, " for more.", size="5")
    if inside == "colored":
        return namespace.text("See ", link, " for more.", color_scheme="ruby")
    if inside == "high-contrast":
        return namespace.text(
            "See ", link, " for more.", color_scheme="ruby", high_contrast=True
        )
    return link


STATES = ["rest", HOVER, FOCUS_VISIBLE]

MATRIX = Matrix(
    component="link",
    render=_link,
    cross={
        "underline": ["auto", "hover", "always", "none"],
        "state": STATES,
    },
    sweep={
        "size": {
            **{size: size for size in "123456789"},
            "responsive": rx.breakpoints(initial="1", sm="6", lg="3"),
        },
        "weight": ["light", "regular", "medium", "bold"],
        "trim": ["normal", "start", "end", "both"],
        "color_scheme": ACCENTS,
        "high_contrast": [True],
        "inside": ["text", "colored", "high-contrast"],
        "holds": ["code", "code-and-words"],
        "is_external": [True],
        "href": {"none": None, "external": "https://reflex.dev"},
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {"high_contrast": [True], "state": STATES, "appearance": ["light", DARK]},
        {
            "color_scheme": ["ruby", "gray"],
            "high_contrast": [False, True],
            "state": STATES,
        },
        {"inside": ["text", "colored", "high-contrast"], "state": STATES},
        {
            "inside": ["colored"],
            "underline": ["hover", "always", "none"],
        },
        {"inside": ["colored"], "color_scheme": ["blue"], "state": STATES},
        {"holds": ["code", "code-and-words"], "state": STATES},
        {"underline": ["always"], "appearance": [DARK], "state": STATES},
        {
            "size": {"responsive": rx.breakpoints(initial="1", sm="6", lg="3")},
            "viewport": [520, 800, 1280],
        },
    ],
    stage=(300, 120),
    target="a",
    crop="stage",
    properties=(
        *Matrix.__dataclass_fields__["properties"].default,
        "text-decoration-style",
        "text-decoration-color",
        "text-decoration-thickness",
        "text-underline-offset",
    ),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="link",
    render=lambda namespace: namespace.box(
        namespace.link("Parity pages", href="/", id="internal"),
        namespace.link("Reflex", href="https://reflex.dev", id="external"),
        namespace.link("New tab", href="/", is_external=True, id="new-tab"),
        namespace.link("Nowhere", id="nowhere"),
    ),
)


@CONTRACT.step("is an anchor with its address in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    internal = run.server.element("internal")
    assert (internal.tag, internal.text) == ("a", "Parity pages")
    assert internal.attributes["href"] == "/"
    external = run.server.element("external")
    assert (external.tag, external.attributes["href"]) == ("a", "https://reflex.dev")
    assert run.server.element("new-tab").attributes["target"] == "_blank"
    assert run.server.element("nowhere").attributes["href"] == "#"


@CONTRACT.step("is a plain link with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    link = run.page.locator("#internal")
    assert link.is_visible()
    link.click()
    run.page.wait_for_url(lambda url: url.rstrip("/").count("/") == 2)


@CONTRACT.step("has the role and the name of a link", on=HYDRATED)
def _role(run: Run) -> None:
    link = run.page.get_by_role("link", name="Parity pages")
    assert link.get_attribute("id") == "internal"


@CONTRACT.step("Tab moves the focus through the links in order", on=HYDRATED)
def _tab(run: Run) -> None:
    focused = []
    for _ in range(4):
        run.page.keyboard.press("Tab")
        focused.append(run.page.evaluate("document.activeElement.id"))
    assert focused == ["internal", "external", "new-tab", "nowhere"]
    assert run.page.locator("#nowhere").evaluate(
        "element => element.matches(':focus-visible')"
    )


@CONTRACT.step("a click navigates without loading the page again", on=HYDRATED)
def _client_side_navigation(run: Run) -> None:
    run.page.evaluate("window.loadedOnce = true")
    run.page.locator("#internal").click()
    run.page.wait_for_url(lambda url: url.rstrip("/").count("/") == 2)
    assert run.page.evaluate("window.loadedOnce") is True


@CONTRACT.step("Enter follows the focused link without a page load", on=HYDRATED)
def _enter(run: Run) -> None:
    run.page.evaluate("window.loadedOnce = true")
    run.page.locator("#internal").focus()
    run.page.keyboard.press("Enter")
    run.page.wait_for_url(lambda url: url.rstrip("/").count("/") == 2)
    assert run.page.evaluate("window.loadedOnce") is True
