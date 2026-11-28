"""Tests for reflex_components_ui.components.switch."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


def test_switch(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A switch is a native checkbox with the role of a switch, its track and thumb drawn by its styles."""
    component = rx.ui.switch(id="wifi", name="wifi", default_checked=True)
    assert component.render() == {
        "name": '"input"',
        "props": [
            "className:sx_14daba69db_c",
            "defaultChecked:true",
            'id:"wifi"',
            'name:"wifi"',
            "ref:ref_wifi",
            'role:"switch"',
            'type:"checkbox"',
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
                    "default": "var(--gray-a3)",
                    ":active:not(:disabled)": "var(--gray-a4)",
                },
                "::after": {"default": "white", ":disabled": "var(--gray-2)"},
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    "default": "linear-gradient(to right, var(--accent-track) 40%, transparent 60%)",
                    ":disabled": "none",
                },
            },
            "boxSizing": "border-box",
            "color": "inherit",
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
            "verticalAlign": "top",
            "flexShrink": 0,
            "height": {
                "default": "var(--line-height, var(--switch-height))",
                "::before": "var(--switch-height)",
                "::after": "var(--switch-thumb-size)",
            },
            "--switch-width": "calc(var(--switch-height) * 1.75)",
            "--switch-thumb-inset": "1px",
            "--switch-thumb-size": "calc(var(--switch-height) - var(--switch-thumb-inset) * 2)",
            "--switch-thumb-translate-x": "calc(var(--switch-width) - var(--switch-height))",
            "cursor": {
                ":disabled": "var(--cursor-disabled)",
                "::before": {
                    "default": "var(--cursor-switch)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "mixBlendMode": {
                ":disabled": "var(--rx-if-light, multiply) var(--rx-if-dark, screen)"
            },
            "content": {"::before": "''", "::after": "''"},
            "width": {
                "::before": "var(--switch-width)",
                "::after": "var(--switch-thumb-size)",
            },
            "borderRadius": {
                "::before": "var(--switch-border-radius)",
                "::after": "calc(var(--switch-border-radius) - var(--switch-thumb-inset))",
            },
            "transitionProperty": {
                "::before": "background-position, background-color, box-shadow, filter",
                "::after": {"default": "transform, box-shadow", ":disabled": "none"},
            },
            "transitionTimingFunction": {
                "::before": "linear, ease-in-out, ease-in-out, ease-in-out",
                "::after": "cubic-bezier(0.45, 0.05, 0.55, 0.95), ease-in-out",
            },
            "transitionDuration": {
                "::before": {
                    "default": "120ms, 140ms, 140ms, 140ms",
                    ":checked": "160ms, 140ms, 140ms, 140ms",
                    ":active": "30ms",
                },
                "::after": "140ms",
            },
            "backgroundRepeat": {"::before": "no-repeat"},
            "backgroundSize": {
                "::before": "calc(var(--switch-width) * 2 + var(--switch-height)) 100%"
            },
            "backgroundPositionX": {"::before": {"default": "100%", ":checked": "0%"}},
            "backgroundPositionY": {"::before": "50%"},
            "left": {"::after": "var(--switch-thumb-inset)"},
            "transform": {
                "::after": {":checked": "translateX(var(--switch-thumb-translate-x))"}
            },
            "pointerEvents": {"::after": "none"},
            "--switch-height": "calc(var(--space-5) * 5 / 6)",
            "--switch-border-radius": "max(var(--radius-2), var(--radius-thumb))",
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-a5)",
                    ":disabled": "inset 0 0 0 1px var(--gray-a3)",
                },
                "::after": {
                    "default": "0 0 1px 1px var(--black-a2), 0 1px 1px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":checked:not(:disabled)": "0 1px 3px var(--black-a2), 0 2px 4px -1px var(--black-a1), 0 0 0 1px var(--black-a1), 0 0 0 1px var(--accent-a4), -1px 0 1px var(--black-a2)",
                    ":disabled": "0 0 0 1px var(--gray-a2), 0 1px 3px var(--black-a1)",
                },
            },
            "filter": {
                "::before": {
                    "default": "none",
                    ":checked:active:not(:disabled)": "var(--rx-if-light, brightness(0.92) saturate(1.1)) var(--rx-if-dark, brightness(1.08))",
                }
            },
        }
    ]


def test_switch_classic_high_contrast(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """Every prop reaches the input or selects its styles, and a switch that nothing changes is read only."""
    component = rx.ui.switch(
        checked=True,
        size=rx.breakpoints(initial="1", md="3"),
        variant="classic",
        high_contrast=True,
        color_scheme="ruby",
        radius="small",
        disabled=True,
        required=True,
        value="yes",
        as_child=True,
    )
    assert component.render() == {
        "name": '"input"',
        "props": [
            "checked:true",
            'className:sx_7350a6aadb_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_6d1e87c3d8',
            "disabled:true",
            "readOnly:true",
            "required:true",
            'role:"switch"',
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
                    "default": "var(--gray-a4)",
                    ":active:not(:checked, :disabled)": "var(--gray-a5)",
                    ":disabled": "var(--gray-a5)",
                },
                "::after": {"default": "white", ":disabled": "var(--gray-2)"},
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    "default": "linear-gradient(to right, light-dark(var(--black-a8), transparent) 40%, transparent 60%), linear-gradient(to right, var(--accent-track) 40%, transparent 60%)",
                    ":disabled": "none",
                },
            },
            "boxSizing": "border-box",
            "color": "inherit",
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
            "verticalAlign": "top",
            "flexShrink": 0,
            "height": {
                "default": "var(--line-height, var(--switch-height))",
                "::before": "var(--switch-height)",
                "::after": "var(--switch-thumb-size)",
            },
            "--switch-width": "calc(var(--switch-height) * 1.75)",
            "--switch-thumb-inset": "1px",
            "--switch-thumb-size": "calc(var(--switch-height) - var(--switch-thumb-inset) * 2)",
            "--switch-thumb-translate-x": "calc(var(--switch-width) - var(--switch-height))",
            "cursor": {
                ":disabled": "var(--cursor-disabled)",
                "::before": {
                    "default": "var(--cursor-switch)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "mixBlendMode": {
                ":disabled": "var(--rx-if-light, multiply) var(--rx-if-dark, screen)"
            },
            "content": {"::before": "''", "::after": "''"},
            "width": {
                "::before": "var(--switch-width)",
                "::after": "var(--switch-thumb-size)",
            },
            "borderRadius": {
                "::before": "var(--switch-border-radius)",
                "::after": "calc(var(--switch-border-radius) - var(--switch-thumb-inset))",
            },
            "transitionProperty": {
                "::before": "background-position, background-color, box-shadow, filter",
                "::after": {"default": "transform, box-shadow", ":disabled": "none"},
            },
            "transitionTimingFunction": {
                "::before": "linear, ease-in-out, ease-in-out, ease-in-out",
                "::after": "cubic-bezier(0.45, 0.05, 0.55, 0.95), ease-in-out",
            },
            "transitionDuration": {
                "::before": {
                    "default": "120ms, 140ms, 140ms, 140ms",
                    ":checked": "160ms, 140ms, 140ms, 140ms",
                    ":active": "30ms",
                },
                "::after": "140ms",
            },
            "backgroundRepeat": {"::before": "no-repeat"},
            "backgroundSize": {
                "::before": "calc(var(--switch-width) * 2 + var(--switch-height)) 100%"
            },
            "backgroundPositionX": {"::before": {"default": "100%", ":checked": "0%"}},
            "backgroundPositionY": {"::before": "50%"},
            "left": {"::after": "var(--switch-thumb-inset)"},
            "transform": {
                "::after": {":checked": "translateX(var(--switch-thumb-translate-x))"}
            },
            "pointerEvents": {"::after": "none"},
            "--switch-height": {
                "default": "var(--space-4)",
                "@media (min-width: 1024px)": "var(--space-5)",
            },
            "--switch-border-radius": {
                "default": "max(var(--radius-1), var(--radius-thumb))",
                "@media (min-width: 1024px)": "max(var(--radius-2), var(--radius-thumb))",
            },
            "boxShadow": {
                "::before": {
                    "default": "inset 0 0 0 1px var(--gray-a3), inset 0 0 0 1px var(--black-a2), inset 0 1.5px 2px 0 var(--black-a2)",
                    ":disabled": "var(--shadow-1)",
                },
                "::after": {
                    "default": "0 1px 3px var(--black-a3), 0 2px 4px -1px var(--black-a1), 0 0 0 1px var(--black-a2)",
                    ":checked:not(:disabled)": "0 1px 3px var(--black-a2), 0 2px 4px -1px var(--black-a1), 0 0 0 1px var(--black-a2), -1px 0 1px var(--black-a2)",
                    ":disabled": "0 0 0 1px var(--gray-a2), 0 1px 3px var(--black-a1)",
                },
            },
            "opacity": {"::before": {"default": 1, ":disabled": 0.5}},
            "filter": {
                "::before": {
                    "default": "none",
                    ":checked:active:not(:disabled)": "var(--rx-if-light, contrast(0.82) saturate(1.2) brightness(1.16)) var(--rx-if-dark, brightness(1.08))",
                }
            },
        }
    ]


def test_switch_soft(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The soft variant layers the gradients of its track and mutes its thumb."""
    component = rx.ui.switch(variant="soft")
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
                    "default": "var(--gray-a3)",
                    ":checked:not(:disabled)": "transparent",
                    ":active:not(:disabled)": "var(--gray-a4)",
                    ":disabled": "var(--gray-a4)",
                },
                "::after": {"default": "white", ":disabled": "var(--gray-2)"},
            },
            "backgroundImage": {
                "default": "none",
                "::before": {
                    "default": "linear-gradient(to right, var(--accent-a4) 40%, transparent 60%), linear-gradient(to right, var(--accent-a4) 40%, transparent 60%), linear-gradient(to right, var(--accent-a4) 40%, var(--white-a1) 60%), linear-gradient(to right, var(--gray-a2) 40%, var(--gray-a3) 60%)",
                    ":disabled": "none",
                },
            },
            "boxSizing": "border-box",
            "color": "inherit",
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
            "verticalAlign": "top",
            "flexShrink": 0,
            "height": {
                "default": "var(--line-height, var(--switch-height))",
                "::before": "var(--switch-height)",
                "::after": "var(--switch-thumb-size)",
            },
            "--switch-width": "calc(var(--switch-height) * 1.75)",
            "--switch-thumb-inset": "1px",
            "--switch-thumb-size": "calc(var(--switch-height) - var(--switch-thumb-inset) * 2)",
            "--switch-thumb-translate-x": "calc(var(--switch-width) - var(--switch-height))",
            "cursor": {
                ":disabled": "var(--cursor-disabled)",
                "::before": {
                    "default": "var(--cursor-switch)",
                    ":disabled": "var(--cursor-disabled)",
                },
            },
            "mixBlendMode": {
                ":disabled": "var(--rx-if-light, multiply) var(--rx-if-dark, screen)"
            },
            "content": {"::before": "''", "::after": "''"},
            "width": {
                "::before": "var(--switch-width)",
                "::after": "var(--switch-thumb-size)",
            },
            "borderRadius": {
                "::before": "var(--switch-border-radius)",
                "::after": "calc(var(--switch-border-radius) - var(--switch-thumb-inset))",
            },
            "transitionProperty": {
                "::before": "background-position, background-color, box-shadow, filter",
                "::after": {"default": "transform, box-shadow", ":disabled": "none"},
            },
            "transitionTimingFunction": {
                "::before": "linear, ease-in-out, ease-in-out, ease-in-out",
                "::after": "cubic-bezier(0.45, 0.05, 0.55, 0.95), ease-in-out",
            },
            "transitionDuration": {
                "::before": {
                    "default": "120ms, 140ms, 140ms, 140ms",
                    ":checked": "160ms, 140ms, 140ms, 140ms",
                    ":active": "30ms",
                },
                "::after": "140ms",
            },
            "backgroundRepeat": {"::before": "no-repeat"},
            "backgroundSize": {
                "::before": "calc(var(--switch-width) * 2 + var(--switch-height)) 100%"
            },
            "backgroundPositionX": {"::before": {"default": "100%", ":checked": "0%"}},
            "backgroundPositionY": {"::before": "50%"},
            "left": {"::after": "var(--switch-thumb-inset)"},
            "transform": {
                "::after": {":checked": "translateX(var(--switch-thumb-translate-x))"}
            },
            "pointerEvents": {"::after": "none"},
            "--switch-height": "calc(var(--space-5) * 5 / 6)",
            "--switch-border-radius": "max(var(--radius-2), var(--radius-thumb))",
            "boxShadow": {
                "::after": {
                    "default": "0 0 0 1px var(--black-a1), 0 1px 3px var(--black-a1), 0 1px 3px var(--black-a1), 0 2px 4px -1px var(--black-a1)",
                    ":checked:not(:disabled)": "0 0 0 1px var(--black-a1), 0 1px 3px var(--black-a2), 0 1px 3px var(--accent-a3), 0 2px 4px -1px var(--accent-a3)",
                    ":disabled": "0 0 0 1px var(--gray-a2), 0 1px 3px var(--black-a1)",
                }
            },
            "filter": {"::after": {"default": "saturate(0.45)", ":disabled": "none"}},
        }
    ]


def test_switch_unknown_variant(ui_plugin: UIPlugin):
    """A variant a switch does not have is an error that lists the ones it has."""
    with pytest.raises(StyleError) as error:
        rx.ui.switch(variant="solid")
    assert (
        str(error.value)
        == 'rx.ui.switch: unknown variant "solid". The values are "classic", "surface", "soft".'
    )


def test_switch_unknown_radius(ui_plugin: UIPlugin):
    """So is a radius: a switch has three."""
    with pytest.raises(StyleError) as error:
        rx.ui.switch(radius="large")
    assert (
        str(error.value)
        == 'rx.ui.switch: unknown radius "large". The values are "none", "small", "full".'
    )
