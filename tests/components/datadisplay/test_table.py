import sys
from typing import List

import pytest

from reflex.components.datadisplay.table import Tbody, Tfoot, Thead
from reflex.state import State


class TableState(State):
    """Test State class."""

    rows_1: List[List[str]] = [["random", "row"]]
    rows_2: List[List] = [["random", "row"]]
    rows_3: List[str] = ["random", "row"]
    rows_4: str = "random, row"
    headers_1: List[str] = ["header1", "header2"]
    headers_2: str = "headers1, headers2"
    footers_1: List[str] = ["footer1", "footer2"]
    footers_2: str = "footer1, footer2"

    if sys.version_info.major >= 3 and sys.version_info.minor > 8:
        rows_5: list[list[str]] = [["random", "row"]]
        rows_6: list[list] = [["random", "row"]]
        rows_7: list[str] = ["random", "row"]


valid_extras = (
    [TableState.rows_5, TableState.rows_6]
    if sys.version_info.major >= 3 and sys.version_info.minor > 7
    else []
)
invalid_extras = [TableState.rows_7]


@pytest.mark.parametrize(
    "rows", [[["random", "row"]], TableState.rows_1, TableState.rows_2, *valid_extras]
)
def test_create_table_body_with_valid_rows_prop(rows):
    render_dict = Tbody.create(rows=rows).render()
    assert render_dict["name"] == "Tbody"
    assert len(render_dict["children"]) == 1


@pytest.mark.parametrize(
    "rows",
    [
        ["random", "row"],
        "random, rows",
        TableState.rows_3,
        TableState.rows_4,
        *invalid_extras,
    ],
)
def test_create_table_body_with_invalid_rows_prop(rows):
    with pytest.raises(TypeError):
        Tbody.create(rows=rows)


@pytest.mark.parametrize(
    "headers",
    [
        ["random", "header"],
        TableState.headers_1,
    ],
)
def test_create_table_head_with_valid_headers_prop(headers):
    render_dict = Thead.create(headers=headers).render()
    assert render_dict["name"] == "Thead"
    assert len(render_dict["children"]) == 1
    assert render_dict["children"][0]["name"] == "Tr"


@pytest.mark.parametrize(
    "headers",
    [
        "random, header",
        TableState.headers_2,
    ],
)
def test_create_table_head_with_invalid_headers_prop(headers):
    with pytest.raises(TypeError):
        Thead.create(headers=headers)


@pytest.mark.parametrize(
    "footers",
    [
        ["random", "footers"],
        TableState.footers_1,
    ],
)
def test_create_table_footer_with_valid_footers_prop(footers):
    render_dict = Tfoot.create(footers=footers).render()
    assert render_dict["name"] == "Tfoot"
    assert len(render_dict["children"]) == 1
    assert render_dict["children"][0]["name"] == "Tr"


@pytest.mark.parametrize(
    "footers",
    [
        "random, footers",
        TableState.footers_2,
    ],
)
def test_create_table_footer_with_invalid_footers_prop(footers):
    with pytest.raises(TypeError):
        Tfoot.create(footers=footers)
