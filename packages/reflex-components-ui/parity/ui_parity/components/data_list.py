"""The data list: labels beside or above their values, in each size and alignment."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix
from ui_parity.samples import ACCENTS, PARAGRAPH

ALIGNS = ["start", "center", "end", "baseline", "stretch"]
ORIENTATIONS = ["horizontal", "vertical"]
SIZES = ["1", "2", "3"]
TRIMS = ["normal", "start", "end", "both"]

# The props of a cell that are those of the label, and of an item.
_LABEL_PROPS = ("color_scheme", "width", "min_width", "max_width")
_ITEM_PROPS = ("align",)


def _values(namespace: Any, content: str) -> list[tuple[str, Any]]:
    """Make the labels and the values of a list.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        content: What the values hold: ``plain`` words, ``long`` text that
            wraps, ``rich`` components, or ``tall`` values, which show how an
            item is aligned.

    Returns:
        Each label with its value.
    """
    if content == "long":
        return [
            ("Description of the animal", PARAGRAPH),
            ("Identifier", "u_2J89JSA4GJ_u_2J89JSA4GJ_u_2J89JSA4GJ_u_2J89JSA4GJ"),
        ]
    if content == "rich":
        return [
            ("Status", rx.badge("Authorized", color_scheme="jade", radius="full")),
            ("ID", namespace.code("u_2J89JSA4GJ")),
            ("Email", namespace.link("fox@example.com", href="#mail")),
            ("Name", namespace.text("Quick Brown Fox", weight="bold")),
        ]
    if content == "tall":
        return [
            (
                "Name",
                rx.el.div("Fox", style={"height": "40px", "outline": "1px solid"}),
            ),
            (
                "Den",
                rx.el.div("Hill", style={"height": "40px", "outline": "1px solid"}),
            ),
            (
                "Food",
                rx.el.div("Hens", style={"height": "40px", "outline": "1px solid"}),
            ),
        ]
    return [("Name", "Quick Brown Fox"), ("Email", "fox@example.com"), ("Den", "Hill")]


def _data_list(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a data list, with the props of a cell on the part they belong to.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``content`` names what the list holds.

    Returns:
        The list.
    """
    props = dict(props)
    content = props.pop("content", "plain")
    label = {name: props.pop(name) for name in _LABEL_PROPS if name in props}
    item = {name: props.pop(name) for name in _ITEM_PROPS if name in props}
    data_list = namespace.data_list
    return data_list.root(
        *[
            data_list.item(
                data_list.label(name, **label), data_list.value(value), **item
            )
            for name, value in _values(namespace, content)
        ],
        **props,
    )


MATRIX = Matrix(
    component="data_list",
    render=_data_list,
    cross={"orientation": ORIENTATIONS, "size": SIZES},
    sweep={
        "trim": TRIMS,
        "align": ALIGNS,
        "content": ["long", "rich", "tall"],
        "color_scheme": ACCENTS,
        "width": ["60px", "200px"],
        "min_width": ["0px", "180px"],
        "max_width": ["30px"],
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {"orientation": ORIENTATIONS, "trim": TRIMS, "size": ["1", "3"]},
        {"orientation": ORIENTATIONS, "align": ALIGNS, "content": ["tall", "long"]},
        {"orientation": ORIENTATIONS, "content": ["long", "rich", "tall"]},
        {"orientation": ORIENTATIONS, "content": ["rich"], "size": SIZES},
        {
            "orientation": ORIENTATIONS,
            "min_width": ["0px", "180px"],
            "width": ["60px"],
        },
        {
            "orientation": ORIENTATIONS,
            "color_scheme": ["ruby", "gray"],
            "appearance": [DARK],
        },
        {"content": ["rich"], "appearance": [DARK]},
        {
            "orientation": {
                "responsive": rx.breakpoints(initial="vertical", sm="horizontal")
            },
            "size": {"responsive": rx.breakpoints(initial="1", xs="3", md="2")},
            "trim": {"responsive": rx.breakpoints(initial="both", sm="start")},
            "align": {"responsive": rx.breakpoints(initial="center", md="end")},
            "width": {"responsive": rx.breakpoints(initial="80px", md="160px")},
            "content": ["plain", "tall"],
            "viewport": [519, 520, 767, 768, 1023, 1024, 1280],
        },
        {
            "orientation": {
                "responsive-vertical": rx.breakpoints(
                    initial="horizontal", sm="vertical"
                )
            },
            "content": ["plain", "long"],
            "viewport": [767, 768],
        },
    ],
    stage=(380, 260),
    parts={
        "item": "dl > div",
        "label": "dt",
        "value": "dd",
        "last item": "dl > div:last-child",
        "last label": "dl > div:last-child dt",
        "last value": "dl > div:last-child dd",
    },
    properties=(
        *Matrix.__dataclass_fields__["properties"].default,
        "grid-template-columns",
        "grid-column-start",
        "grid-column-end",
        "overflow-wrap",
    ),
    threshold=0,
    tolerance=0,
)

CONTRACT = Contract(
    component="data_list",
    render=lambda namespace: namespace.data_list.root(
        namespace.data_list.item(
            namespace.data_list.label("Name", id="name-label"),
            namespace.data_list.value("Quick Brown Fox", id="name-value"),
            id="name",
        ),
        namespace.data_list.item(
            namespace.data_list.label("Email", id="email-label"),
            namespace.data_list.value(
                rx.el.a("fox@example.com", href="#mail", id="mail"),
                id="email-value",
            ),
        ),
        id="list",
    ),
)


@CONTRACT.step(
    "is a description list of terms and details in the server render", on=SERVER
)
def _server_render(run: Run) -> None:
    root = run.server.element("list")
    assert (root.tag, root.text) == ("dl", "NameQuick Brown FoxEmailfox@example.com")
    item = run.server.element("name")
    assert (item.tag, item.text) == ("div", "NameQuick Brown Fox")
    label = run.server.element("name-label")
    assert (label.tag, label.text) == ("dt", "Name")
    value = run.server.element("name-value")
    assert (value.tag, value.text) == ("dd", "Quick Brown Fox")


def _laid_out(run: Run) -> None:
    """Check that each label is beside its value, and the labels are one column.

    Args:
        run: The run of the step.
    """
    name, value, email, mail = (
        run.page.locator(f"#{element}").evaluate(
            "element => element.getBoundingClientRect().toJSON()"
        )
        for element in ("name-label", "name-value", "email-label", "email-value")
    )
    # The implicit width of a label, then the gap of the size.
    assert (name["x"], name["width"]) == (email["x"], 120)
    assert value["x"] == mail["x"] == name["x"] + 120 + 16
    assert email["y"] > name["y"]


@CONTRACT.step(
    "lays out labels beside values with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#list").inner_text() == (
        "Name\nQuick Brown Fox\nEmail\nfox@example.com"
    )
    _laid_out(run)


@CONTRACT.step("lays out labels beside values after hydration", on=HYDRATED)
def _hydrated(run: Run) -> None:
    _laid_out(run)


@CONTRACT.step("has the roles of terms and their definitions", on=HYDRATED)
def _roles(run: Run) -> None:
    terms = run.page.get_by_role("term")
    assert [terms.nth(index).get_attribute("id") for index in range(2)] == [
        "name-label",
        "email-label",
    ]
    definitions = run.page.get_by_role("definition")
    assert [definitions.nth(index).get_attribute("id") for index in range(2)] == [
        "name-value",
        "email-value",
    ]


@CONTRACT.step("Tab reaches what a value holds", on=HYDRATED)
def _tab(run: Run) -> None:
    run.page.keyboard.press("Tab")
    assert run.page.evaluate("document.activeElement.id") == "mail"
