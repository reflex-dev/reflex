"""The table: a header, row headers and cells, in each variant and size."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import reflex as rx
from ui_parity.contract import HYDRATED, NO_JAVASCRIPT, SERVER, Contract, Run
from ui_parity.matrix import DARK, LIGHT, Matrix
from ui_parity.samples import PARAGRAPH

PEOPLE = (
    ("Danilo Sousa", "danilo@example.com", "Developer"),
    ("Zahra Ambessa", "zahra@example.com", "Admin"),
    ("Jasper Eriksson", "jasper@example.com", "Developer"),
)
RESPONSIVE = rx.breakpoints(initial="1", sm="3", lg="2")


def _table(namespace: Any, props: Mapping[str, Any]) -> Any:
    """Create a table of people, with what a cell says of its rows and cells.

    Args:
        namespace: ``rx`` or ``rx.ui``.
        props: The props of the cell. ``row`` and ``cell`` hold the props of
            every row of the body and of every cell, ``header`` the ones of
            the header cells, and ``content`` names what the cells hold.

    Returns:
        The table.
    """
    props = dict(props)
    row = props.pop("row", {})
    cell = props.pop("cell", {})
    header = props.pop("header", {})
    content = props.pop("content", "short")
    table = namespace.table
    people = PEOPLE
    if content == "long":
        people = ((PEOPLE[0][0], PARAGRAPH, "Developer"), *PEOPLE[1:])
    if content == "wide":
        people = tuple(
            (name, f"{email} · {email} · {email}", role) for name, email, role in PEOPLE
        )
    return table.root(
        table.header(
            table.row(
                *(
                    table.column_header_cell(title, **header)
                    for title in ("Full name", "Email", "Group")
                )
            )
        ),
        table.body(
            *(
                table.row(
                    table.row_header_cell(name, **cell),
                    table.cell(email, **cell),
                    table.cell(role, **cell),
                    **row,
                )
                for name, email, role in people
            )
        ),
        **props,
    )


MATRIX = Matrix(
    component="table",
    render=_table,
    cross={"variant": ["ghost", "surface"], "size": ["1", "2", "3"]},
    sweep={
        "size": {"responsive": RESPONSIVE},
        "content": ["long", "wide"],
        "row": {
            f"align-{align}": {"align": align}
            for align in ("start", "center", "end", "baseline")
        },
        "cell": {
            **{
                f"justify-{justify}": {"justify": justify}
                for justify in ("start", "center", "end")
            },
            "p-4": {"p": "4"},
            "px-0": {"px": "0"},
            "py-1": {"py": "1"},
            "sides": {"pt": "1", "pr": "2", "pb": "3", "pl": "4"},
            "min-width": {"min_width": "200px"},
            "max-width": {"max_width": "60px"},
            "responsive": {
                "p": rx.breakpoints(initial="1", sm="4"),
                "min_width": rx.breakpoints(initial="60px", sm="180px"),
            },
        },
        "header": {
            "justify-end": {"justify": "end"},
            "min-width": {"min_width": "200px"},
        },
        "appearance": [DARK],
        "viewport": [520],
    },
    groups=[
        {
            "variant": ["ghost", "surface"],
            "content": ["long", "wide"],
            "appearance": [LIGHT, DARK],
        },
        {
            "row": {"align-center": {"align": "center"}, "align-end": {"align": "end"}},
            "content": ["long"],
            "variant": ["ghost", "surface"],
        },
        {
            "size": {"responsive": RESPONSIVE},
            "variant": ["ghost", "surface"],
            "viewport": [520, 800, 1100, 1280],
        },
        {
            "cell": {
                "responsive": {
                    "p": rx.breakpoints(initial="1", sm="4"),
                    "min_width": rx.breakpoints(initial="60px", sm="180px"),
                }
            },
            "viewport": [520, 800],
        },
    ],
    stage=(480, 300),
    crop="stage",
    parts={
        "table": "table",
        "header": "thead",
        "body": "tbody",
        "row": "tbody tr",
        "last row": "tbody tr:last-child",
        "column header": "thead th",
        "row header": "tbody th",
        "cell": "td",
        "last cell": "tbody tr:last-child td",
    },
    # No pixel may differ, at the default threshold and not at zero. At a
    # threshold of zero the 37 cells of the ghost variant are equal, and the
    # 13 of the surface variant differ by one step of a channel in a band of
    # the header: its see-through background lies over the see-through panel
    # of the table, and the two systems put a different number of boxes
    # between them, which the browser blends in another order.
    tolerance=0,
)

CONTRACT = Contract(
    component="table",
    render=lambda namespace: namespace.table.root(
        namespace.table.header(
            namespace.table.row(
                namespace.table.column_header_cell("Full name", id="name"),
                namespace.table.column_header_cell("Group"),
                id="head",
            ),
            id="header",
        ),
        namespace.table.body(
            namespace.table.row(
                namespace.table.row_header_cell("Danilo Sousa", id="danilo"),
                namespace.table.cell("Developer", id="group"),
            ),
            id="body",
        ),
        id="root",
    ),
)


@CONTRACT.step("is a table of rows and cells in the server render", on=SERVER)
def _server_render(run: Run) -> None:
    assert run.server.element("root").tag == "div"
    assert run.server.element("header").tag == "thead"
    assert run.server.element("body").tag == "tbody"
    assert (run.server.element("head").tag, run.server.element("head").text) == (
        "tr",
        "Full nameGroup",
    )
    assert run.server.element("name").tag == "th"
    assert run.server.element("danilo").tag == "th"
    group = run.server.element("group")
    assert (group.tag, group.text) == ("td", "Developer")


@CONTRACT.step(
    "lays its cells out in columns with JavaScript disabled", on=NO_JAVASCRIPT
)
def _without_javascript(run: Run) -> None:
    _columns(run)


@CONTRACT.step("has the roles of a table, its headers and its cells", on=HYDRATED)
def _roles(run: Run) -> None:
    _columns(run)
    page = run.page
    assert page.get_by_role("table").count() == 1
    assert page.get_by_role("rowgroup").count() == 2
    assert page.get_by_role("row").count() == 2
    assert page.get_by_role("columnheader").all_inner_texts() == ["Full name", "Group"]
    assert page.get_by_role("rowheader").all_inner_texts() == ["Danilo Sousa"]
    assert page.get_by_role("cell").all_inner_texts() == ["Developer"]


def _columns(run: Run) -> None:
    """Check that a cell is under its column header, beside its row header.

    Args:
        run: The run of the step.
    """
    name = run.page.locator("#name").bounding_box()
    danilo = run.page.locator("#danilo").bounding_box()
    group = run.page.locator("#group").bounding_box()
    assert name is not None
    assert danilo is not None
    assert group is not None
    assert (danilo["x"], danilo["width"]) == (name["x"], name["width"])
    assert danilo["y"] == name["y"] + name["height"]
    assert (group["y"], group["x"]) == (danilo["y"], danilo["x"] + danilo["width"])
