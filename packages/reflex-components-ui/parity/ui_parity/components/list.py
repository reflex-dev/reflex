"""Lists: ordered, unordered and plain, their markers and their items."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, Matrix

ITEMS = ["The quick brown fox", "jumps over", "the lazy dog"]


def _list(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a list of one kind, from items or from children.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``kind`` names the helper that creates
            the list, and ``children`` what its items hold.

    Returns:
        The list.
    """
    props = dict(props)
    kind = props.pop("kind", "unordered")
    children = props.pop("children", "items")
    create = namespace.list if kind == "plain" else getattr(namespace.list, kind)
    if children == "items":
        return create(items=ITEMS, **props)
    if children == "rich":
        return create(
            namespace.list.item(
                rx.icon("circle_check", size=14), namespace.text("Tested", size="2")
            ),
            namespace.list.item(
                namespace.text("Read ", weight="bold"),
                namespace.link("the docs", href="/docs"),
            ),
            namespace.list.item("Run ", namespace.code("uv sync")),
            **props,
        )
    return create(
        namespace.list.item(
            "Fruits", namespace.list.unordered(items=["Apples", "Pears"])
        ),
        namespace.list.item("Vegetables", namespace.list.ordered(items=["Leeks"])),
        **props,
    )


MATRIX = Matrix(
    component="list",
    render=_list,
    cross={
        "kind": ["unordered", "ordered", "plain"],
        "children": ["items", "rich", "nested"],
    },
    sweep={
        "list_style_type": ["none", "disc", "circle", "square"],
        "style": {"spaced": {"padding_left": "8px", "color": "gray"}},
        "margin_left": ["0px", "3rem"],
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "kind": ["ordered"],
            "list_style_type": [
                "none",
                "decimal",
                "decimal-leading-zero",
                "lower-roman",
                "upper-roman",
                "lower-greek",
                "lower-latin",
                "upper-latin",
                "armenian",
                "georgian",
                "lower-alpha",
                "upper-alpha",
                "hiragana",
                "katakana",
            ],
        },
        {"kind": ["plain"], "list_style_type": ["disc", "decimal"]},
    ],
    stage=(260, 200),
    parts={"item": "li"},
    properties=(
        *Matrix.__dataclass_fields__["properties"].default,
        "list-style-type",
        "list-style-position",
    ),
)

CONTRACT = Contract(
    component="list",
    render=lambda namespace: namespace.box(
        namespace.list.unordered(items=["one", "two"], id="unordered"),
        namespace.list.ordered(
            namespace.list.item("first", id="first"), namespace.list.item("second"),
            id="ordered",
        ),
    ),
)


@CONTRACT.step("is a list of items in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    unordered = run.server.element("unordered")
    assert (unordered.tag, unordered.text) == ("ul", "onetwo")
    assert run.server.element("ordered").tag == "ol"
    first = run.server.element("first")
    assert (first.tag, first.text) == ("li", "first")


@CONTRACT.step("is shown with JavaScript disabled", on=NO_JAVASCRIPT)
def _without_javascript(run: Run) -> None:
    assert run.page.locator("#unordered").inner_text() == "one\ntwo"


@CONTRACT.step("has the roles of lists and their items", on=HYDRATED)
def _roles(run: Run) -> None:
    lists = run.page.get_by_role("list")
    assert [lists.nth(index).get_attribute("id") for index in range(2)] == [
        "unordered",
        "ordered",
    ]
    assert run.page.get_by_role("listitem").count() == 4
