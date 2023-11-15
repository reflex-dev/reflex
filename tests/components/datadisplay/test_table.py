import sys
from typing import List, Tuple

import pytest

from nextpy.components.datadisplay.table import Tbody, Tfoot, Thead
from nextpy.core.state import State

PYTHON_GT_V38 = sys.version_info.major >= 3 and sys.version_info.minor > 8


class TableState(State):
    """Test State class."""

    rows_List_List_str: List[List[str]] = [["random", "row"]]
    rows_List_List: List[List] = [["random", "row"]]
    rows_List_str: List[str] = ["random", "row"]
    rows_Tuple_List_str: Tuple[List[str]] = (["random", "row"],)
    rows_Tuple_List: Tuple[List] = ["random", "row"]  # type: ignore
    rows_Tuple_str_str: Tuple[str, str] = (
        "random",
        "row",
    )
    rows_Tuple_Tuple_str_str: Tuple[Tuple[str, str]] = (
        (
            "random",
            "row",
        ),
    )
    rows_Tuple_Tuple: Tuple[Tuple] = (
        (
            "random",
            "row",
        ),
    )
    rows_str: str = "random, row"
    headers_List_str: List[str] = ["header1", "header2"]
    headers_Tuple_str_str: Tuple[str, str] = (
        "header1",
        "header2",
    )
    headers_str: str = "headers1, headers2"
    footers_List_str: List[str] = ["footer1", "footer2"]
    footers_Tuple_str_str: Tuple[str, str] = (
        "footer1",
        "footer2",
    )
    footers_str: str = "footer1, footer2"

    if sys.version_info.major >= 3 and sys.version_info.minor > 8:
        rows_list_list_str: list[list[str]] = [["random", "row"]]
        rows_list_list: list[list] = [["random", "row"]]
        rows_list_str: list[str] = ["random", "row"]
        rows_tuple_list_str: tuple[list[str]] = (["random", "row"],)
        rows_tuple_list: tuple[list] = ["random", "row"]  # type: ignore
        rows_tuple_str_str: tuple[str, str] = (
            "random",
            "row",
        )
        rows_tuple_tuple_str_str: tuple[tuple[str, str]] = (
            (
                "random",
                "row",
            ),
        )
        rows_tuple_tuple: tuple[tuple] = (
            (
                "random",
                "row",
            ),
        )


valid_extras = (
    [
        TableState.rows_list_list_str,
        TableState.rows_list_list,
        TableState.rows_tuple_list_str,
        TableState.rows_tuple_list,
        TableState.rows_tuple_tuple_str_str,
        TableState.rows_tuple_tuple,
    ]
    if PYTHON_GT_V38
    else []
)
invalid_extras = (
    [TableState.rows_list_str, TableState.rows_tuple_str_str] if PYTHON_GT_V38 else []
)


@pytest.mark.parametrize(
    "rows",
    [
        [["random", "row"]],
        TableState.rows_List_List_str,
        TableState.rows_List_List,
        TableState.rows_Tuple_List_str,
        TableState.rows_Tuple_List,
        TableState.rows_Tuple_Tuple_str_str,
        TableState.rows_Tuple_Tuple,
        *valid_extras,
    ],
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
        TableState.rows_List_str,
        TableState.rows_Tuple_str_str,
        TableState.rows_str,
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
        TableState.headers_List_str,
        TableState.headers_Tuple_str_str,
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
        TableState.headers_str,
    ],
)
def test_create_table_head_with_invalid_headers_prop(headers):
    with pytest.raises(TypeError):
        Thead.create(headers=headers)


@pytest.mark.parametrize(
    "footers",
    [
        ["random", "footers"],
        TableState.footers_List_str,
        TableState.footers_Tuple_str_str,
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
        TableState.footers_str,
    ],
)
def test_create_table_footer_with_invalid_footers_prop(footers):
    with pytest.raises(TypeError):
        Tfoot.create(footers=footers)
