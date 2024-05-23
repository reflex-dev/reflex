from __future__ import annotations

from typing import Any

import pytest

import reflex as rx
from reflex import style
from reflex.components.component import evaluate_style_namespaces
from reflex.style import Style
from reflex.vars import Var, VarData

test_style = [
    ({"a": 1}, {"a": 1}),
    ({"a": Var.create("abc")}, {"a": "abc"}),
    ({"test_case": 1}, {"testCase": 1}),
    ({"test_case": {"a": 1}}, {"testCase": {"a": 1}}),
    ({":test_case": {"a": 1}}, {":testCase": {"a": 1}}),
    ({"::test_case": {"a": 1}}, {"::testCase": {"a": 1}}),
    (
        {"::-webkit-scrollbar": {"display": "none"}},
        {"::-webkit-scrollbar": {"display": "none"}},
    ),
    ({"margin_y": "2rem"}, {"marginBottom": "2rem", "marginTop": "2rem"}),
    ({"marginY": "2rem"}, {"marginBottom": "2rem", "marginTop": "2rem"}),
    (
        {"::-webkit-scrollbar": {"bgColor": "red"}},
        {"::-webkit-scrollbar": {"backgroundColor": "red"}},
    ),
    (
        {"paddingX": ["2rem", "3rem"]},
        {
            "paddingInlineStart": ["2rem", "3rem"],
            "paddingInlineEnd": ["2rem", "3rem"],
        },
    ),
]


@pytest.mark.parametrize(
    "style_dict,expected",
    test_style,
)
def test_convert(style_dict, expected):
    """Test Format a style dictionary.

    Args:
        style_dict: The style to check.
        expected: The expected formatted style.
    """
    converted_dict, _var_data = style.convert(style_dict)
    assert converted_dict == expected


@pytest.mark.parametrize(
    "style_dict,expected",
    test_style,
)
def test_create_style(style_dict, expected):
    """Test style dictionary.

    Args:
        style_dict: The style to check.
        expected: The expected formatted style.
    """
    assert style.Style(style_dict) == expected


def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
    """Compare two dictionaries of Var objects.

    Args:
        d1: The first dictionary.
        d2: The second dictionary.
    """
    assert len(d1) == len(d2)
    for key, value in d1.items():
        assert key in d2
        if isinstance(value, dict):
            compare_dict_of_var(value, d2[key])
        elif isinstance(value, Var):
            assert value.equals(d2[key])
        else:
            assert value == d2[key]


@pytest.mark.parametrize(
    ("kwargs", "style_dict", "expected_get_style"),
    [
        ({}, {}, {"css": None}),
        ({"color": "hotpink"}, {}, {"css": Var.create(Style({"color": "hotpink"}))}),
        ({}, {"color": "red"}, {"css": Var.create(Style({"color": "red"}))}),
        (
            {"color": "hotpink"},
            {"color": "red"},
            {"css": Var.create(Style({"color": "hotpink"}))},
        ),
        (
            {"_hover": {"color": "hotpink"}},
            {},
            {"css": Var.create(Style({"&:hover": {"color": "hotpink"}}))},
        ),
        (
            {},
            {"_hover": {"color": "red"}},
            {"css": Var.create(Style({"&:hover": {"color": "red"}}))},
        ),
        (
            {},
            {":hover": {"color": "red"}},
            {"css": Var.create(Style({"&:hover": {"color": "red"}}))},
        ),
        (
            {},
            {"::-webkit-scrollbar": {"display": "none"}},
            {"css": Var.create(Style({"&::-webkit-scrollbar": {"display": "none"}}))},
        ),
        (
            {},
            {"::-moz-progress-bar": {"background_color": "red"}},
            {
                "css": Var.create(
                    Style({"&::-moz-progress-bar": {"backgroundColor": "red"}})
                )
            },
        ),
        (
            {"color": ["#111", "#222", "#333", "#444", "#555"]},
            {},
            {
                "css": Var.create(
                    Style(
                        {
                            "@media screen and (min-width: 0)": {"color": "#111"},
                            "@media screen and (min-width: 30em)": {"color": "#222"},
                            "@media screen and (min-width: 48em)": {"color": "#333"},
                            "@media screen and (min-width: 62em)": {"color": "#444"},
                            "@media screen and (min-width: 80em)": {"color": "#555"},
                        }
                    )
                )
            },
        ),
        (
            {
                "color": ["#111", "#222", "#333", "#444", "#555"],
                "background_color": "#FFF",
            },
            {},
            {
                "css": Var.create(
                    Style(
                        {
                            "@media screen and (min-width: 0)": {"color": "#111"},
                            "@media screen and (min-width: 30em)": {"color": "#222"},
                            "@media screen and (min-width: 48em)": {"color": "#333"},
                            "@media screen and (min-width: 62em)": {"color": "#444"},
                            "@media screen and (min-width: 80em)": {"color": "#555"},
                            "backgroundColor": "#FFF",
                        }
                    )
                )
            },
        ),
        (
            {
                "color": ["#111", "#222", "#333", "#444", "#555"],
                "background_color": ["#FFF", "#EEE", "#DDD", "#CCC", "#BBB"],
            },
            {},
            {
                "css": Var.create(
                    Style(
                        {
                            "@media screen and (min-width: 0)": {
                                "color": "#111",
                                "backgroundColor": "#FFF",
                            },
                            "@media screen and (min-width: 30em)": {
                                "color": "#222",
                                "backgroundColor": "#EEE",
                            },
                            "@media screen and (min-width: 48em)": {
                                "color": "#333",
                                "backgroundColor": "#DDD",
                            },
                            "@media screen and (min-width: 62em)": {
                                "color": "#444",
                                "backgroundColor": "#CCC",
                            },
                            "@media screen and (min-width: 80em)": {
                                "color": "#555",
                                "backgroundColor": "#BBB",
                            },
                        }
                    )
                )
            },
        ),
        (
            {
                "_hover": [
                    {"color": "#111"},
                    {"color": "#222"},
                    {"color": "#333"},
                    {"color": "#444"},
                    {"color": "#555"},
                ]
            },
            {},
            {
                "css": Var.create(
                    Style(
                        {
                            "&:hover": {
                                "@media screen and (min-width: 0)": {"color": "#111"},
                                "@media screen and (min-width: 30em)": {
                                    "color": "#222"
                                },
                                "@media screen and (min-width: 48em)": {
                                    "color": "#333"
                                },
                                "@media screen and (min-width: 62em)": {
                                    "color": "#444"
                                },
                                "@media screen and (min-width: 80em)": {
                                    "color": "#555"
                                },
                            }
                        }
                    )
                )
            },
        ),
        (
            {"_hover": {"color": ["#111", "#222", "#333", "#444", "#555"]}},
            {},
            {
                "css": Var.create(
                    Style(
                        {
                            "&:hover": {
                                "@media screen and (min-width: 0)": {"color": "#111"},
                                "@media screen and (min-width: 30em)": {
                                    "color": "#222"
                                },
                                "@media screen and (min-width: 48em)": {
                                    "color": "#333"
                                },
                                "@media screen and (min-width: 62em)": {
                                    "color": "#444"
                                },
                                "@media screen and (min-width: 80em)": {
                                    "color": "#555"
                                },
                            }
                        }
                    )
                )
            },
        ),
        (
            {
                "_hover": {
                    "color": ["#111", "#222", "#333", "#444", "#555"],
                    "background_color": ["#FFF", "#EEE", "#DDD", "#CCC", "#BBB"],
                }
            },
            {},
            {
                "css": Var.create(
                    Style(
                        {
                            "&:hover": {
                                "@media screen and (min-width: 0)": {
                                    "color": "#111",
                                    "backgroundColor": "#FFF",
                                },
                                "@media screen and (min-width: 30em)": {
                                    "color": "#222",
                                    "backgroundColor": "#EEE",
                                },
                                "@media screen and (min-width: 48em)": {
                                    "color": "#333",
                                    "backgroundColor": "#DDD",
                                },
                                "@media screen and (min-width: 62em)": {
                                    "color": "#444",
                                    "backgroundColor": "#CCC",
                                },
                                "@media screen and (min-width: 80em)": {
                                    "color": "#555",
                                    "backgroundColor": "#BBB",
                                },
                            }
                        }
                    )
                )
            },
        ),
        (
            {
                "_hover": {
                    "color": ["#111", "#222", "#333", "#444", "#555"],
                    "background_color": "#FFF",
                }
            },
            {},
            {
                "css": Var.create(
                    Style(
                        {
                            "&:hover": {
                                "@media screen and (min-width: 0)": {"color": "#111"},
                                "@media screen and (min-width: 30em)": {
                                    "color": "#222"
                                },
                                "@media screen and (min-width: 48em)": {
                                    "color": "#333"
                                },
                                "@media screen and (min-width: 62em)": {
                                    "color": "#444"
                                },
                                "@media screen and (min-width: 80em)": {
                                    "color": "#555"
                                },
                                "backgroundColor": "#FFF",
                            }
                        }
                    )
                )
            },
        ),
    ],
)
def test_style_via_component(
    kwargs: dict[str, Any],
    style_dict: dict[str, Any],
    expected_get_style: dict[str, Any],
):
    """Pass kwargs and style_dict to a component and assert the final, combined style dict.

    Args:
        kwargs: The kwargs to pass to the component.
        style_dict: The style_dict to pass to the component.
        expected_get_style: The expected style dict.
    """
    comp = rx.el.div(style=style_dict, **kwargs)  # type: ignore
    compare_dict_of_var(comp._get_style(), expected_get_style)


class StyleState(rx.State):
    """Style vars in a substate."""

    color: str = "hotpink"
    color2: str = "red"


@pytest.mark.parametrize(
    ("kwargs", "expected_get_style"),
    [
        (
            {"color": StyleState.color},
            {"css": Var.create(Style({"color": StyleState.color}))},
        ),
        (
            {"color": f"dark{StyleState.color}"},
            {
                "css": Var.create_safe(f'{{"color": `dark{StyleState.color}`}}').to(
                    Style
                )
            },
        ),
        (
            {"color": StyleState.color, "_hover": {"color": StyleState.color2}},
            {
                "css": Var.create(
                    Style(
                        {
                            "color": StyleState.color,
                            "&:hover": {"color": StyleState.color2},
                        }
                    )
                )
            },
        ),
        (
            {"color": [StyleState.color, "gray", StyleState.color2, "yellow", "blue"]},
            {
                "css": Var.create(
                    Style(
                        {
                            "@media screen and (min-width: 0)": {
                                "color": StyleState.color
                            },
                            "@media screen and (min-width: 30em)": {"color": "gray"},
                            "@media screen and (min-width: 48em)": {
                                "color": StyleState.color2
                            },
                            "@media screen and (min-width: 62em)": {"color": "yellow"},
                            "@media screen and (min-width: 80em)": {"color": "blue"},
                        }
                    )
                )
            },
        ),
        (
            {
                "_hover": [
                    {"color": StyleState.color},
                    {"color": StyleState.color2},
                    {"color": "#333"},
                    {"color": "#444"},
                    {"color": "#555"},
                ]
            },
            {
                "css": Var.create(
                    Style(
                        {
                            "&:hover": {
                                "@media screen and (min-width: 0)": {
                                    "color": StyleState.color
                                },
                                "@media screen and (min-width: 30em)": {
                                    "color": StyleState.color2
                                },
                                "@media screen and (min-width: 48em)": {
                                    "color": "#333"
                                },
                                "@media screen and (min-width: 62em)": {
                                    "color": "#444"
                                },
                                "@media screen and (min-width: 80em)": {
                                    "color": "#555"
                                },
                            }
                        }
                    )
                )
            },
        ),
        (
            {
                "_hover": {
                    "color": [
                        StyleState.color,
                        StyleState.color2,
                        "#333",
                        "#444",
                        "#555",
                    ]
                }
            },
            {
                "css": Var.create(
                    Style(
                        {
                            "&:hover": {
                                "@media screen and (min-width: 0)": {
                                    "color": StyleState.color
                                },
                                "@media screen and (min-width: 30em)": {
                                    "color": StyleState.color2
                                },
                                "@media screen and (min-width: 48em)": {
                                    "color": "#333"
                                },
                                "@media screen and (min-width: 62em)": {
                                    "color": "#444"
                                },
                                "@media screen and (min-width: 80em)": {
                                    "color": "#555"
                                },
                            }
                        }
                    )
                )
            },
        ),
    ],
)
def test_style_via_component_with_state(
    kwargs: dict[str, Any],
    expected_get_style: dict[str, Any],
):
    """Pass kwargs to a component with state vars and assert the final, combined style dict.

    Args:
        kwargs: The kwargs to pass to the component.
        expected_get_style: The expected style dict.
    """
    comp = rx.el.div(**kwargs)

    assert comp.style._var_data == expected_get_style["css"]._var_data
    # Assert that style values are equal.
    compare_dict_of_var(comp._get_style(), expected_get_style)


def test_evaluate_style_namespaces():
    """Test that namespaces get converted to component create functions."""
    style_dict = {rx.text: {"color": "blue"}}
    assert rx.text.__call__ not in style_dict
    style_dict = evaluate_style_namespaces(style_dict)  # type: ignore
    assert rx.text.__call__ in style_dict


def test_style_update_with_var_data():
    """Test that .update with a Style containing VarData works."""
    red_var = Var.create_safe("red")._replace(
        merge_var_data=VarData(hooks={"const red = true": None}),  # type: ignore
    )
    blue_var = Var.create_safe("blue", _var_is_local=False)._replace(
        merge_var_data=VarData(hooks={"const blue = true": None}),  # type: ignore
    )

    s1 = Style(
        {
            "color": red_var,
        }
    )
    s2 = Style()
    s2.update(s1, background_color=f"{blue_var}ish")
    assert s2 == {"color": "red", "backgroundColor": "`${blue}ish`"}
    assert s2._var_data is not None
    assert "const red = true" in s2._var_data.hooks
    assert "const blue = true" in s2._var_data.hooks
