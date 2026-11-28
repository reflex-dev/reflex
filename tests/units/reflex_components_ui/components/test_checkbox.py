"""Tests for reflex_components_ui.components.checkbox."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.components.checkbox import Checkbox
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


class CheckboxState(rx.State):
    """What a checkbox is bound to."""

    agreed: bool = False

    @rx.event
    def agree(self, agreed: bool):
        """Follow the checkbox.

        Args:
            agreed: Whether it is checked.
        """
        self.agreed = agreed


def test_checkbox_with_its_label(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A checkbox is a native input in a label, with its text beside it."""
    component = rx.ui.checkbox("Agree", id="agree", name="agree")
    assert component.render() == {
        "name": '"label"',
        "props": ["className:sx_d1083f6dbf_c"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_1362d43b5f_c"],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            "className:sx_b87bd44530_c",
                            'id:"agree"',
                            'name:"agree"',
                            "ref:ref_agree",
                            'type:"checkbox"',
                        ],
                        "children": [],
                    },
                    {"contents": '"Agree"'},
                ],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "fontSize": "var(--font-size-2)",
            "--line-height": "var(--line-height-2)",
            "--letter-spacing": "var(--letter-spacing-2)",
            "WebkitTapHighlightColor": {"@media (pointer: coarse)": "transparent"},
            "outlineWidth": {"@media (pointer: coarse)": {":active": "0.75em"}},
            "outlineStyle": {"@media (pointer: coarse)": {":active": "solid"}},
            "outlineColor": {"@media (pointer: coarse)": {":active": "var(--gray-a4)"}},
            "outlineOffset": {"@media (pointer: coarse)": {":active": "-0.6em"}},
        },
        {
            "boxSizing": "border-box",
            "display": "flex",
            "justifyContent": "flex-start",
            "rowGap": "var(--space-2)",
            "columnGap": "var(--space-2)",
        },
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "backgroundColor": {
                "default": "transparent",
                "::before": {
                    "default": "var(--color-surface)",
                    ":is(:checked, :indeterminate):not(:disabled)": "var(--accent-indicator)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": "currentcolor",
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": {
                "default": "inherit",
                "::after": {
                    "default": "var(--accent-contrast)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": "var(--space-4)",
            "--checkbox-indicator-size": "calc(10px * var(--scaling))",
            "--checkbox-border-radius": "var(--radius-1)",
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-a7)",
                    ":is(:checked, :indeterminate):not(:disabled)": "none",
                    ":disabled": "inset 0 0 0 1px var(--gray-a6)",
                }
            },
        },
    ]


def test_checkbox_alone(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """Every prop reaches the input or selects its styles, and a checkbox that nothing changes is read only."""
    component = Checkbox.create(
        checked=True,
        size=rx.breakpoints(initial="1", md="3"),
        variant="soft",
        high_contrast=True,
        color_scheme="ruby",
        disabled=True,
        required=True,
        value="yes",
        as_child=True,
    )
    assert component.render() == {
        "name": '"input"',
        "props": [
            "checked:true",
            'className:sx_6ac964b510_c + " " + reflexUIClasses_e201574881',
            "disabled:true",
            "readOnly:true",
            "required:true",
            'type:"checkbox"',
            'value:"yes"',
        ],
        "children": [],
    }
    assert declared_styles(component) == [
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "backgroundColor": {
                "default": "transparent",
                "::before": {
                    "default": "var(--accent-a5)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": "currentcolor",
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": {
                "default": "inherit",
                "::after": {
                    "default": "var(--accent-12)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": {
                "default": "calc(var(--space-4) * 0.875)",
                "@media (min-width: 1024px)": "calc(var(--space-4) * 1.25)",
            },
            "--checkbox-indicator-size": {
                "default": "calc(9px * var(--scaling))",
                "@media (min-width: 1024px)": "calc(12px * var(--scaling))",
            },
            "--checkbox-border-radius": {
                "default": "calc(var(--radius-1) * 0.875)",
                "@media (min-width: 1024px)": "calc(var(--radius-1) * 1.25)",
            },
        }
    ]


def test_checkbox_classic(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The classic variant has a gradient and the shadows of a raised box."""
    component = Checkbox.create(variant="classic", default_checked=True)
    assert declared_styles(component) == [
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "paddingTop": "0",
            "paddingRight": "0",
            "paddingBottom": "0",
            "paddingLeft": "0",
            "borderTopWidth": "0",
            "borderRightWidth": "0",
            "borderBottomWidth": "0",
            "borderLeftWidth": "0",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "backgroundColor": {
                "default": "transparent",
                "::before": {
                    "default": "var(--color-surface)",
                    ":is(:checked, :indeterminate):not(:disabled)": "var(--accent-indicator)",
                    ":disabled": "var(--gray-a3)",
                },
                "::after": "currentcolor",
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    "default": "none",
                    ":is(:checked, :indeterminate):not(:disabled)": "linear-gradient(to bottom, var(--white-a3), transparent, var(--black-a1))",
                },
            },
            "boxSizing": "border-box",
            "color": {
                "default": "inherit",
                "::after": {
                    "default": "var(--accent-contrast)",
                    ":disabled": "var(--gray-a8)",
                },
            },
            "fontSize": "inherit",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "textIndent": "initial",
            "outlineStyle": {
                "default": "none",
                "::before": {":focus-visible": "solid"},
            },
            "outlineWidth": {
                "default": "medium",
                "::before": {":focus-visible": "2px"},
            },
            "outlineColor": {
                "default": "currentcolor",
                "::before": {":focus-visible": "var(--focus-8)"},
            },
            "outlineOffset": {"default": "0", "::before": {":focus-visible": "2px"}},
            "WebkitTapHighlightColor": "transparent",
            "position": {"default": "relative", "::after": "absolute"},
            "display": {"default": "inline-flex", "::before": "block"},
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "top",
            "flexShrink": 0,
            "cursor": {
                "default": "var(--cursor-checkbox)",
                ":disabled": "var(--cursor-disabled)",
            },
            "height": {
                "default": "var(--line-height, var(--checkbox-size))",
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "content": {
                "::before": "''",
                "::after": {":is(:checked, :indeterminate)": "''"},
            },
            "width": {
                "::before": "var(--checkbox-size)",
                "::after": "var(--checkbox-indicator-size)",
            },
            "borderRadius": {"::before": "var(--checkbox-border-radius)"},
            "transform": {"::after": "translate(-50%, -50%)"},
            "top": {"::after": "50%"},
            "left": {"::after": "50%"},
            "pointerEvents": {"::after": "none"},
            "maskImage": {
                "::after": {
                    "default": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z'/%3E%3C/svg%3E\")",
                    ":indeterminate": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 9 9'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M0.75 4.5C0.75 4.08579 1.08579 3.75 1.5 3.75H7.5C7.91421 3.75 8.25 4.08579 8.25 4.5C8.25 4.91421 7.91421 5.25 7.5 5.25H1.5C1.08579 5.25 0.75 4.91421 0.75 4.5Z'/%3E%3C/svg%3E\")",
                }
            },
            "maskSize": {"::after": "100% 100%"},
            "maskRepeat": {"::after": "no-repeat"},
            "--checkbox-size": "var(--space-4)",
            "--checkbox-indicator-size": "calc(10px * var(--scaling))",
            "--checkbox-border-radius": "var(--radius-1)",
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-a3), var(--shadow-1)",
                    ":is(:checked, :indeterminate):not(:disabled)": "inset 0 0.5px 0.5px var(--white-a4), inset 0 -0.5px 0.5px var(--black-a4)",
                    ":disabled": "var(--shadow-1)",
                }
            },
        }
    ]


def test_checkbox_spacing_and_gap(
    ui_plugin: UIPlugin,
):
    """The spacing and the gap are the ones of the row of the label."""
    component = rx.ui.checkbox("Agree", spacing="4", gap="1px", size="3")
    assert component.render() == {
        "name": '"label"',
        "props": ["className:sx_3c18f01562_c"],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_6778334529_c"],
                "children": [
                    {
                        "name": '"input"',
                        "props": ["className:sx_846aafb601_c", 'type:"checkbox"'],
                        "children": [],
                    },
                    {"contents": '"Agree"'},
                ],
            }
        ],
    }


def test_checkbox_unknown_variant(ui_plugin: UIPlugin):
    """A variant a checkbox does not have is an error that lists the ones it has."""
    with pytest.raises(StyleError) as error:
        rx.ui.checkbox("Agree", variant="solid")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == 'rx.ui.checkbox: unknown variant "solid". The values are "classic", "surface", "soft".'
    )


def test_checkbox_unknown_size(ui_plugin: UIPlugin):
    """So is a size."""
    with pytest.raises(StyleError) as error:
        rx.ui.checkbox("Agree", size="4")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == 'rx.ui.checkbox: unknown size "4". The values are "1", "2", "3".'
    )
