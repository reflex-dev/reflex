"""Tests for reflex_components_ui.typography.link."""

from collections.abc import Callable
from typing import Any

from reflex_components_ui.plugin import UIPlugin

import reflex as rx


def test_link_internal(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A link with an address is the link of the router, with the styles of the link."""
    component = rx.ui.link("a", href="/docs")
    assert component.render() == {
        "name": "ReactRouterLink",
        "props": ["className:sx_b8b1ea03e8_c", 'to:"/docs"'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "color": {
                "default": "var(--rx-accent-link, var(--accent-a11))",
                ":hover": "var(--accent-8)",
            },
            "WebkitTapHighlightColor": "transparent",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": {
                ":any-link": "var(--cursor-link)",
                "[data-disabled]": "var(--cursor-disabled)",
            },
            "textDecorationStyle": "solid",
            "textDecorationThickness": "min(2px, max(1px, 0.05em))",
            "textUnderlineOffset": "calc(0.025em + 2px)",
            "textDecorationColor": {
                "default": "var(--rx-accent-link-line-color, color-mix(in "
                "oklab, var(--accent-a5), var(--gray-a6)))",
                ':has(code[data-variant]:not([data-variant="ghost"]):only-child)': "transparent",
            },
            "borderRadius": {":focus-visible": "calc(0.07em * var(--radius-factor))"},
            "outlineColor": {
                ":focus-visible": "var(--focus-8)",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "var(--accent-a4)"
                },
            },
            "outlineWidth": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "0.75em"
                },
            },
            "outlineStyle": {
                ":focus-visible": "solid",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "solid"
                },
            },
            "outlineOffset": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "-0.6em"
                },
            },
            "--rx-link-code-solid": "var(--accent-10)",
            "--rx-link-code-soft": "var(--accent-a4)",
            "--rx-link-code-outline": "var(--accent-a2)",
            "--rx-link-code-filter": (
                "var(--rx-if-light, contrast(0.88) saturate(1.1) brightness(1.1)) "
                "var(--rx-if-dark, contrast(0.88) saturate(1.3) brightness(1.18))"
            ),
            "textDecorationLine": {
                "default": "var(--rx-accent-link-line, none)",
                ":focus-visible": "none",
                "@media (hover: hover)": {
                    ":hover": "underline",
                    ":focus-visible": "none",
                },
            },
        }
    ]


def test_link_no_href(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """Without an address it is an anchor that goes nowhere."""
    component = rx.ui.link(
        "a", underline="always", size="2", weight="medium", trim="both"
    )
    assert component.render() == {
        "name": '"a"',
        "props": ["className:sx_ee879616af_c", 'href:"#"'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": {
                "default": "0",
                "::after": "calc(var(--leading-trim-end, "
                "var(--default-leading-trim-end)) - var(--line-height, "
                "calc(1em * var(--default-line-height))) / 2)",
            },
            "marginRight": "0",
            "marginBottom": {
                "default": "0",
                "::before": "calc(var(--leading-trim-start, "
                "var(--default-leading-trim-start)) - "
                "var(--line-height, calc(1em * "
                "var(--default-line-height))) / 2)",
            },
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "color": {
                "default": "var(--rx-accent-link, var(--accent-a11))",
                ":hover": "var(--accent-8)",
            },
            "WebkitTapHighlightColor": "transparent",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": {
                ":any-link": "var(--cursor-link)",
                "[data-disabled]": "var(--cursor-disabled)",
            },
            "textDecorationStyle": "solid",
            "textDecorationThickness": "min(2px, max(1px, 0.05em))",
            "textUnderlineOffset": "calc(0.025em + 2px)",
            "textDecorationColor": {
                "default": "color-mix(in oklab, var(--accent-a5), var(--gray-a6))",
                ':has(code[data-variant]:not([data-variant="ghost"]):only-child)': "transparent",
            },
            "borderRadius": {":focus-visible": "calc(0.07em * var(--radius-factor))"},
            "outlineColor": {
                ":focus-visible": "var(--focus-8)",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "var(--accent-a4)"
                },
            },
            "outlineWidth": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "0.75em"
                },
            },
            "outlineStyle": {
                ":focus-visible": "solid",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "solid"
                },
            },
            "outlineOffset": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "-0.6em"
                },
            },
            "--rx-link-code-solid": "var(--accent-10)",
            "--rx-link-code-soft": "var(--accent-a4)",
            "--rx-link-code-outline": "var(--accent-a2)",
            "--rx-link-code-filter": (
                "var(--rx-if-light, contrast(0.88) saturate(1.1) brightness(1.1)) "
                "var(--rx-if-dark, contrast(0.88) saturate(1.3) brightness(1.18))"
            ),
            "fontSize": "var(--font-size-2)",
            "--line-height": "var(--line-height-2)",
            "--letter-spacing": "var(--letter-spacing-2)",
            "fontWeight": "var(--font-weight-medium)",
            "content": {"::before": "''", "::after": "''"},
            "display": {"::before": "table", "::after": "table"},
            "textDecorationLine": {
                "default": "underline",
                ":focus-visible": "none",
                "@media (hover: hover)": {
                    ":hover": "underline",
                    ":focus-visible": "none",
                },
            },
        }
    ]


def test_link_external(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """The props of the router go to its link, the others to the element."""
    component = rx.ui.link(
        "a",
        href="https://reflex.dev",
        is_external=True,
        reload_document=True,
        id="home",
        color_scheme="ruby",
        high_contrast=True,
        underline="hover",
    )
    assert component.render() == {
        "name": "ReactRouterLink",
        "props": [
            'className:sx_271b4725e7_c + " " + reflexUIClasses_e201574881',
            'id:"home"',
            "ref:ref_home",
            "reloadDocument:true",
            'target:(true ? "_blank" : "")',
            'to:"https://reflex.dev"',
        ],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "color": {"default": "var(--accent-12)", ":hover": "var(--accent-8)"},
            "WebkitTapHighlightColor": "transparent",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": {
                ":any-link": "var(--cursor-link)",
                "[data-disabled]": "var(--cursor-disabled)",
            },
            "textDecorationStyle": "solid",
            "textDecorationThickness": "min(2px, max(1px, 0.05em))",
            "textUnderlineOffset": "calc(0.025em + 2px)",
            "textDecorationColor": {
                "default": "color-mix(in oklab, var(--accent-a5), var(--gray-a6))",
                ':has(code[data-variant]:not([data-variant="ghost"]):only-child)': "transparent",
            },
            "borderRadius": {":focus-visible": "calc(0.07em * var(--radius-factor))"},
            "outlineColor": {
                ":focus-visible": "var(--focus-8)",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "var(--accent-a4)"
                },
            },
            "outlineWidth": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "0.75em"
                },
            },
            "outlineStyle": {
                ":focus-visible": "solid",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "solid"
                },
            },
            "outlineOffset": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "-0.6em"
                },
            },
            "--rx-link-code-solid": "var(--accent-10)",
            "--rx-link-code-soft": "var(--accent-a4)",
            "--rx-link-code-outline": "var(--accent-a2)",
            "--rx-link-code-filter": (
                "var(--rx-if-light, contrast(0.88) saturate(1.1) brightness(1.1)) "
                "var(--rx-if-dark, contrast(0.88) saturate(1.3) brightness(1.18))"
            ),
            "textDecorationLine": {
                "default": "none",
                ":focus-visible": "none",
                "@media (hover: hover)": {
                    ":hover": "underline",
                    ":focus-visible": "none",
                },
            },
            "--rx-accent-text": "var(--accent-12)",
            "--rx-accent-link": "var(--accent-12)",
            "--rx-accent-link-line": "underline",
            "--rx-accent-link-line-color": "color-mix(in oklab, var(--accent-a6), "
            "var(--gray-a6))",
        }
    ]


def test_link_as_child(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """With as_child the only child is the element."""
    component = rx.ui.link(
        rx.el.button("a"), as_child=True, underline="none", _hover={"color": "red"}
    )
    assert component.render() == {
        "name": '"button"',
        "props": ["className:sx_8321e25311_c", 'href:"#"'],
        "children": [{"contents": '"a"'}],
    }
    assert declared_styles(component) == [
        {
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "lineHeight": "var(--line-height, var(--default-line-height))",
            "letterSpacing": "var(--letter-spacing, inherit)",
            "color": {
                "default": "var(--rx-accent-link, var(--accent-a11))",
                ":hover": "red",
            },
            "WebkitTapHighlightColor": "transparent",
            "borderTopStyle": "none",
            "borderRightStyle": "none",
            "borderBottomStyle": "none",
            "borderLeftStyle": "none",
            "cursor": {
                ":any-link": "var(--cursor-link)",
                "[data-disabled]": "var(--cursor-disabled)",
            },
            "textDecorationStyle": "solid",
            "textDecorationThickness": "min(2px, max(1px, 0.05em))",
            "textUnderlineOffset": "calc(0.025em + 2px)",
            "textDecorationColor": {
                "default": "color-mix(in oklab, var(--accent-a5), var(--gray-a6))",
                ':has(code[data-variant]:not([data-variant="ghost"]):only-child)': "transparent",
            },
            "borderRadius": {":focus-visible": "calc(0.07em * var(--radius-factor))"},
            "outlineColor": {
                ":focus-visible": "var(--focus-8)",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "var(--accent-a4)"
                },
            },
            "outlineWidth": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "0.75em"
                },
            },
            "outlineStyle": {
                ":focus-visible": "solid",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "solid"
                },
            },
            "outlineOffset": {
                ":focus-visible": "2px",
                "@media (pointer: coarse)": {
                    ":active:not(:focus-visible, [data-state='open'])": "-0.6em"
                },
            },
            "--rx-link-code-solid": "var(--accent-10)",
            "--rx-link-code-soft": "var(--accent-a4)",
            "--rx-link-code-outline": "var(--accent-a2)",
            "--rx-link-code-filter": (
                "var(--rx-if-light, contrast(0.88) saturate(1.1) brightness(1.1)) "
                "var(--rx-if-dark, contrast(0.88) saturate(1.3) brightness(1.18))"
            ),
            "textDecorationLine": "none",
        }
    ]
