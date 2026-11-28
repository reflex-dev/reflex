"""Tests for reflex_components_ui.components.table."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.components.component import Component
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def people(**props: Any) -> Component:
    """Create a table of one person.

    Args:
        **props: The props of the root.

    Returns:
        The table.
    """
    table = rx.ui.table
    return table.root(
        table.header(table.row(table.column_header_cell("Name", min_width="80px"))),
        table.body(
            table.row(
                table.row_header_cell("Ada", justify="center"),
                table.cell(
                    "Admin",
                    justify="end",
                    px="4",
                    max_width=rx.breakpoints(initial="60px", md="120px"),
                ),
                align="center",
            )
        ),
        **props,
    )


def test_table_ghost(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A table is a block around a box that scrolls, around the table itself."""
    component = people(id="people")
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_bd7098de3f_c", 'id:"people"', "ref:ref_people"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_d0de57eb68_c"],
                "children": [
                    {
                        "name": '"div"',
                        "props": ["className:sx_b06d947c7c_c"],
                        "children": [
                            {
                                "name": '"table"',
                                "props": ["className:sx_9d58645f70_c"],
                                "children": [
                                    {
                                        "name": '"thead"',
                                        "props": ["className:sx_280fdd8cb1_c"],
                                        "children": [
                                            {
                                                "name": '"tr"',
                                                "props": ["className:sx_4dca3cb40d_c"],
                                                "children": [
                                                    {
                                                        "name": '"th"',
                                                        "props": [
                                                            "className:sx_679f7a88f7_c"
                                                        ],
                                                        "children": [
                                                            {"contents": '"Name"'}
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    {
                                        "name": '"tbody"',
                                        "props": ["className:sx_03514a22c2_c"],
                                        "children": [
                                            {
                                                "name": '"tr"',
                                                "props": ["className:sx_00a8b9e2b4_c"],
                                                "children": [
                                                    {
                                                        "name": '"th"',
                                                        "props": [
                                                            "className:sx_6e04c0def9_c"
                                                        ],
                                                        "children": [
                                                            {"contents": '"Ada"'}
                                                        ],
                                                    },
                                                    {
                                                        "name": '"td"',
                                                        "props": [
                                                            "className:sx_dd497830d2_c"
                                                        ],
                                                        "children": [
                                                            {"contents": '"Admin"'}
                                                        ],
                                                    },
                                                ],
                                            }
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "--table-border-radius": "var(--radius-4)",
            "--table-cell-padding": "var(--space-3)",
            "--table-cell-min-height": "calc(44px * var(--scaling))",
        },
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexDirection": "column",
            "position": "relative",
            "width": "100%",
            "height": "100%",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) var(--gray-a3)",
            "outlineWidth": {":focus-visible": "2px"},
            "outlineStyle": {":focus-visible": "solid"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "outlineOffset": {":focus-visible": "-2px"},
            "overflowX": "auto",
            "overflowY": "auto",
            "overscrollBehaviorX": "contain",
        },
        {
            "boxSizing": "border-box",
            "display": "block",
            "width": "fit-content",
            "minWidth": "100%",
            "flexGrow": 1,
        },
        {
            "--table-row-background-color": "transparent",
            "--table-row-box-shadow": "inset 0 -1px var(--gray-a5)",
            "width": "100%",
            "textAlign": "left",
            "verticalAlign": "top",
            "borderCollapse": "collapse",
            "borderRadius": "calc(var(--table-border-radius) - 1px)",
            "borderSpacing": "0",
            "boxSizing": "border-box",
            "height": "0",
            "fontSize": "var(--font-size-2)",
            "lineHeight": "var(--line-height-2)",
        },
        {
            "verticalAlign": "inherit",
            "--table-row-background-color": "var(--rx-table-header-background, transparent)",
        },
        {
            "verticalAlign": "inherit",
            "color": "var(--gray-12)",
            "--table-row-box-shadow": {
                ":last-child": "var(--rx-table-last-row-shadow, inset 0 "
                "-1px var(--gray-a5))"
            },
        },
        {
            "backgroundColor": "var(--table-row-background-color)",
            "boxShadow": "var(--table-row-box-shadow)",
            "boxSizing": "border-box",
            "verticalAlign": "inherit",
            "padding": "var(--table-cell-padding)",
            "height": "var(--table-cell-min-height)",
            "fontWeight": "bold",
            "minWidth": "80px",
        },
        {
            "verticalAlign": "inherit",
            "--rx-table-last-row-shadow": "var(--rx-table-body-last-row-shadow, inset 0 -1px "
            "var(--gray-a5))",
        },
        {
            "verticalAlign": "middle",
            "color": "var(--gray-12)",
            "--table-row-box-shadow": {
                ":last-child": "var(--rx-table-last-row-shadow, inset 0 "
                "-1px var(--gray-a5))"
            },
        },
        {
            "backgroundColor": "var(--table-row-background-color)",
            "boxShadow": "var(--table-row-box-shadow)",
            "boxSizing": "border-box",
            "verticalAlign": "inherit",
            "padding": "var(--table-cell-padding)",
            "height": "var(--table-cell-min-height)",
            "fontWeight": "normal",
            "textAlign": "center",
        },
        {
            "backgroundColor": "var(--table-row-background-color)",
            "boxShadow": "var(--table-row-box-shadow)",
            "boxSizing": "border-box",
            "verticalAlign": "inherit",
            "padding": "var(--table-cell-padding)",
            "height": "var(--table-cell-min-height)",
            "textAlign": "right",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "maxWidth": {"default": "60px", "@media (min-width: 1024px)": "120px"},
        },
    ]


def test_table_surface(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A surface table tells its header its background, and its body to drop its last line."""
    component = people(variant="surface", size=rx.breakpoints(initial="1", md="3"))
    assert declared_styles(component) == [
        {
            "--table-border-radius": {
                "default": "var(--radius-3)",
                "@media (min-width: 1024px)": "var(--radius-4)",
            },
            "--table-cell-padding": {
                "default": "var(--space-2)",
                "@media (min-width: 1024px)": "var(--space-3) var(--space-4)",
            },
            "--table-cell-min-height": {
                "default": "calc(36px * var(--scaling))",
                "@media (min-width: 1024px)": "var(--space-8)",
            },
            "boxSizing": "border-box",
            "borderTopWidth": "1px",
            "borderRightWidth": "1px",
            "borderBottomWidth": "1px",
            "borderLeftWidth": "1px",
            "borderTopStyle": "solid",
            "borderRightStyle": "solid",
            "borderBottomStyle": "solid",
            "borderLeftStyle": "solid",
            "borderColor": "color-mix(in oklab, var(--gray-a5), var(--gray-6))",
            "borderRadius": "var(--table-border-radius)",
            "backgroundColor": "var(--color-panel)",
            "backdropFilter": "var(--backdrop-filter-panel)",
            "backgroundClip": "padding-box",
            "position": "relative",
            "--rx-table-header-background": "var(--gray-a2)",
            "--rx-table-body-last-row-shadow": "none",
        },
        {
            "boxSizing": "border-box",
            "display": "flex",
            "flexDirection": "column",
            "position": "relative",
            "width": "100%",
            "height": "100%",
            "scrollbarWidth": "thin",
            "scrollbarColor": "var(--gray-a8) var(--gray-a3)",
            "outlineWidth": {":focus-visible": "2px"},
            "outlineStyle": {":focus-visible": "solid"},
            "outlineColor": {":focus-visible": "var(--focus-8)"},
            "outlineOffset": {":focus-visible": "-2px"},
            "overflowX": "auto",
            "overflowY": "auto",
            "overscrollBehaviorX": "contain",
        },
        {
            "boxSizing": "border-box",
            "display": "block",
            "width": "fit-content",
            "minWidth": "100%",
            "flexGrow": 1,
        },
        {
            "--table-row-background-color": "transparent",
            "--table-row-box-shadow": "inset 0 -1px var(--gray-a5)",
            "width": "100%",
            "textAlign": "left",
            "verticalAlign": "top",
            "borderCollapse": "collapse",
            "borderRadius": "calc(var(--table-border-radius) - 1px)",
            "borderSpacing": "0",
            "boxSizing": "border-box",
            "height": "0",
            "fontSize": {
                "default": "var(--font-size-2)",
                "@media (min-width: 1024px)": "var(--font-size-3)",
            },
            "lineHeight": {
                "default": "var(--line-height-2)",
                "@media (min-width: 1024px)": "var(--line-height-3)",
            },
            "overflowX": "hidden",
            "overflowY": "hidden",
        },
        {
            "verticalAlign": "inherit",
            "--table-row-background-color": "var(--rx-table-header-background, transparent)",
        },
        {
            "verticalAlign": "inherit",
            "color": "var(--gray-12)",
            "--table-row-box-shadow": {
                ":last-child": "var(--rx-table-last-row-shadow, inset 0 "
                "-1px var(--gray-a5))"
            },
        },
        {
            "backgroundColor": "var(--table-row-background-color)",
            "boxShadow": "var(--table-row-box-shadow)",
            "boxSizing": "border-box",
            "verticalAlign": "inherit",
            "padding": "var(--table-cell-padding)",
            "height": "var(--table-cell-min-height)",
            "fontWeight": "bold",
            "minWidth": "80px",
        },
        {
            "verticalAlign": "inherit",
            "--rx-table-last-row-shadow": "var(--rx-table-body-last-row-shadow, inset 0 -1px "
            "var(--gray-a5))",
        },
        {
            "verticalAlign": "middle",
            "color": "var(--gray-12)",
            "--table-row-box-shadow": {
                ":last-child": "var(--rx-table-last-row-shadow, inset 0 "
                "-1px var(--gray-a5))"
            },
        },
        {
            "backgroundColor": "var(--table-row-background-color)",
            "boxShadow": "var(--table-row-box-shadow)",
            "boxSizing": "border-box",
            "verticalAlign": "inherit",
            "padding": "var(--table-cell-padding)",
            "height": "var(--table-cell-min-height)",
            "fontWeight": "normal",
            "textAlign": "center",
        },
        {
            "backgroundColor": "var(--table-row-background-color)",
            "boxShadow": "var(--table-row-box-shadow)",
            "boxSizing": "border-box",
            "verticalAlign": "inherit",
            "padding": "var(--table-cell-padding)",
            "height": "var(--table-cell-min-height)",
            "textAlign": "right",
            "paddingLeft": "var(--space-4)",
            "paddingRight": "var(--space-4)",
            "maxWidth": {"default": "60px", "@media (min-width: 1024px)": "120px"},
        },
    ]


def test_table_header_goes_in_a_table():
    """A header or a body outside a table root is an error where it is placed."""
    with pytest.raises(ValueError, match="TableHeader") as raised:
        rx.ui.box(rx.ui.table.header())
    assert str(raised.value) == (
        "The component `TableHeader` can only be a child of the components: "
        "`TableRootTable`. Got `Box` instead."
    )
