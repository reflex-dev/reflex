"""Tests for reflex_components_ui.components.data_list."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx

TRIM = "var(--rx-data-list-value-trim, 0px)"

ROOT_TEXT = {
    "marginTop": "0",
    "marginRight": "0",
    "marginBottom": "0",
    "marginLeft": "0",
    "lineHeight": "var(--line-height, var(--default-line-height))",
    "letterSpacing": "var(--letter-spacing, inherit)",
    "overflowWrap": "anywhere",
    "fontFamily": "var(--default-font-family)",
    "fontStyle": "normal",
    "textAlign": "start",
}

ITEM_LAYOUT = {
    "display": "var(--rx-data-list-item-display, block)",
    "flexDirection": "var(--rx-data-list-item-direction, row)",
    "gridTemplateColumns": "var(--rx-data-list-item-columns, none)",
    "gridColumnStart": "var(--rx-data-list-item-span, auto)",
}

ITEM_SPACE = {
    "rowGap": "var(--rx-data-list-item-gap, inherit)",
    "columnGap": "var(--rx-data-list-item-gap, inherit)",
    "marginTop": {":first-child": "var(--leading-trim-start)"},
    "marginBottom": {":last-child": "var(--leading-trim-end)"},
}

VALUE = {
    "display": "flex",
    "marginLeft": "0",
    "marginRight": "0",
    "marginTop": "var(--data-list-value-margin-top, 0px)",
    "marginBottom": "var(--data-list-value-margin-bottom, 0px)",
    "minWidth": "0px",
    "content": {"::before": "'‍'"},
}


def test_data_list_plain(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A data list is a grid of two columns, which its items take over."""
    data_list = rx.ui.data_list
    component = data_list.root(
        data_list.item(data_list.label("Name"), data_list.value("Fox"))
    )
    assert component.render() == {
        "name": '"dl"',
        "props": ["className:sx_b3965b5abf_c"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_0d6d130655_c"],
                "children": [
                    {
                        "name": '"dt"',
                        "props": ["className:sx_dbeafabcc8_c"],
                        "children": [{"contents": '"Name"'}],
                    },
                    {
                        "name": '"dd"',
                        "props": ["className:sx_01ce835e4e_c"],
                        "children": [{"contents": '"Fox"'}],
                    },
                ],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            **ROOT_TEXT,
            "fontSize": "var(--font-size-2)",
            "--line-height": "var(--line-height-2)",
            "--letter-spacing": "var(--letter-spacing-2)",
            "rowGap": "var(--space-4)",
            "columnGap": "var(--space-4)",
            "display": "grid",
            "gridTemplateColumns": "auto 1fr",
            "--rx-data-list-item-display": "grid",
            "--rx-data-list-item-direction": "row",
            "--rx-data-list-item-columns": "subgrid",
            "--rx-data-list-item-span": "span 2",
            "--rx-data-list-item-align": "baseline",
            "--rx-data-list-item-gap": "initial",
            "--rx-data-list-value-trim": "-0.25em",
            "--rx-data-list-label-min-width": "120px",
        },
        {
            **ITEM_LAYOUT,
            "alignItems": "var(--rx-data-list-item-align, normal)",
            **ITEM_SPACE,
            "--data-list-value-margin-top": {"default": TRIM, ":first-child": "0px"},
            "--data-list-value-margin-bottom": {"default": TRIM, ":last-child": "0px"},
        },
        {
            "display": "flex",
            "color": "var(--gray-a11)",
            "minWidth": "var(--rx-data-list-label-min-width)",
            "content": {"::before": "'‍'"},
        },
        VALUE,
    ]


def test_data_list_props(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Each part has its props, and the style of a label wins over its width props."""
    data_list = rx.ui.data_list
    component = data_list.root(
        data_list.item(
            data_list.label(
                "Name",
                color_scheme="ruby",
                width="80px",
                min_width=rx.breakpoints(initial="0px", md="120px"),
                max_width="50%",
                style={"width": "90px"},
            ),
            data_list.value("Fox"),
            align=rx.breakpoints(initial="center", sm="stretch"),
        ),
        orientation="vertical",
        size="3",
        trim="both",
    )
    assert component.render() == {
        "name": '"dl"',
        "props": ["className:sx_2832f8b266_c"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_b7d48fc98e_c"],
                "children": [
                    {
                        "name": '"dt"',
                        "props": [
                            'className:sx_8bfbd8b1bf_c + " " + reflexUIClasses_e201574881'
                        ],
                        "children": [{"contents": '"Name"'}],
                    },
                    {
                        "name": '"dd"',
                        "props": ["className:sx_01ce835e4e_c"],
                        "children": [{"contents": '"Fox"'}],
                    },
                ],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            **ROOT_TEXT,
            "fontSize": "var(--font-size-3)",
            "--line-height": "var(--line-height-3)",
            "--letter-spacing": "var(--letter-spacing-3)",
            "rowGap": "calc(var(--space-4) * 1.25)",
            "columnGap": "calc(var(--space-4) * 1.25)",
            "display": "flex",
            "flexDirection": "column",
            "--rx-data-list-item-display": "flex",
            "--rx-data-list-item-direction": "column",
            "--rx-data-list-item-columns": "none",
            "--rx-data-list-item-span": "auto",
            "--rx-data-list-item-align": "normal",
            "--rx-data-list-item-gap": "var(--space-1)",
            "--rx-data-list-value-trim": "0px",
            "--rx-data-list-label-min-width": "0px",
            "--leading-trim-start": (
                "calc(var(--default-leading-trim-start) - var(--line-height) / 2)"
            ),
            "--leading-trim-end": (
                "calc(var(--default-leading-trim-end) - var(--line-height) / 2)"
            ),
        },
        {
            **ITEM_LAYOUT,
            "alignItems": {"default": "center", "@media (min-width: 768px)": "stretch"},
            **ITEM_SPACE,
            "--data-list-value-margin-top": {
                "default": TRIM,
                ":first-child": TRIM,
                "@media (min-width: 768px)": {"default": "0px", ":first-child": "0px"},
            },
            "--data-list-value-margin-bottom": {
                "default": TRIM,
                ":last-child": TRIM,
                "@media (min-width: 768px)": {"default": "0px", ":last-child": "0px"},
            },
        },
        {
            "display": "flex",
            "color": "var(--accent-a11)",
            "minWidth": {"default": "0px", "@media (min-width: 1024px)": "120px"},
            "content": {"::before": "'‍'"},
            "--rx-accent-text": "var(--accent-12)",
            "--rx-accent-link": "var(--accent-12)",
            "--rx-accent-link-line": "underline",
            "--rx-accent-link-line-color": (
                "color-mix(in oklab, var(--accent-a6), var(--gray-a6))"
            ),
            "maxWidth": "50%",
            "width": "90px",
        },
        VALUE,
    ]


def test_data_list_responsive(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The props of the list change at a breakpoint, and what it tells its parts with them."""
    component = rx.ui.data_list.root(
        orientation=rx.breakpoints(initial="vertical", sm="horizontal"),
        size=rx.breakpoints(initial="1", lg="3"),
        trim=rx.breakpoints(initial="start", xs="normal"),
    )
    assert component.render() == {
        "name": '"dl"',
        "props": ["className:sx_a6a26de24f_c"],
        "children": [],
    }
    wide, large = "@media (min-width: 768px)", "@media (min-width: 1280px)"
    assert declared_styles(component) == [
        {
            **ROOT_TEXT,
            "fontSize": {"default": "var(--font-size-1)", large: "var(--font-size-3)"},
            "--line-height": {
                "default": "var(--line-height-1)",
                large: "var(--line-height-3)",
            },
            "--letter-spacing": {
                "default": "var(--letter-spacing-1)",
                large: "var(--letter-spacing-3)",
            },
            "rowGap": {
                "default": "var(--space-3)",
                large: "calc(var(--space-4) * 1.25)",
            },
            "columnGap": {
                "default": "var(--space-3)",
                large: "calc(var(--space-4) * 1.25)",
            },
            "display": {"default": "flex", wide: "grid"},
            "flexDirection": {"default": "column", wide: "revert-layer"},
            "--rx-data-list-item-display": {"default": "flex", wide: "grid"},
            "--rx-data-list-item-direction": {"default": "column", wide: "row"},
            "--rx-data-list-item-columns": {"default": "none", wide: "subgrid"},
            "--rx-data-list-item-span": {"default": "auto", wide: "span 2"},
            "--rx-data-list-item-align": {"default": "normal", wide: "baseline"},
            "--rx-data-list-item-gap": {"default": "var(--space-1)", wide: "initial"},
            "--rx-data-list-value-trim": {"default": "0px", wide: "-0.25em"},
            "--rx-data-list-label-min-width": {"default": "0px", wide: "120px"},
            "--leading-trim-start": {
                "default": (
                    "calc(var(--default-leading-trim-start) - var(--line-height) / 2)"
                ),
                "@media (min-width: 520px)": "initial",
            },
            "--leading-trim-end": "initial",
            "gridTemplateColumns": {wide: "auto 1fr"},
        }
    ]


def test_data_list_unknown_values(ui_plugin: UIPlugin):
    """A value a prop does not take names the component and the values it takes."""
    with pytest.raises(StyleError) as error:
        rx.ui.data_list.root(orientation="diagonal")  # pyright: ignore[reportArgumentType]
    assert str(error.value) == (
        'rx.ui.data_list_root: unknown orientation "diagonal". '
        'The values are "horizontal", "vertical".'
    )
    with pytest.raises(StyleError) as error:
        rx.ui.data_list.item(align="middle")  # pyright: ignore[reportArgumentType]
    assert str(error.value) == (
        'rx.ui.data_list_item: unknown align "middle". '
        'The values are "start", "center", "end", "baseline", "stretch".'
    )
