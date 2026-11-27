"""Tests for reflex_components_ui.components.avatar."""

from collections.abc import Callable
from typing import Any

from reflex_base.utils.imports import ImportVar
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


class AvatarState(rx.State):
    """What an avatar is bound to."""

    initials: str = "AB"


def test_avatar_fallback_alone(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """Without a src an avatar is its fallback, sized by its two letters."""
    component = rx.ui.avatar(fallback="AB")
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_eecdbf58c4_c"],
        "children": [
            {
                "name": '"span"',
                "props": ["className:sx_d9c345d227_c"],
                "children": [{"contents": '"AB"'}],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "middle",
            "userSelect": "none",
            "width": "var(--avatar-size)",
            "height": "var(--avatar-size)",
            "flexShrink": 0,
            "--avatar-size": "var(--space-7)",
            "--avatar-fallback-one-letter-font-size": "var(--font-size-4)",
            "borderRadius": "max(var(--radius-3), var(--radius-full))",
            "letterSpacing": "var(--letter-spacing-3)",
            "--avatar-fallback-two-letters-font-size": "var(--font-size-3)",
        },
        {
            "boxSizing": "border-box",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-medium)",
            "fontStyle": "normal",
            "zIndex": 0,
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "lineHeight": 1,
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "textTransform": "uppercase",
            "flexShrink": 0,
            "visibility": {"[data-status='loaded']": "hidden"},
            "fontSize": "var(--avatar-fallback-two-letters-font-size, "
            "var(--avatar-fallback-one-letter-font-size))",
            "backgroundColor": "var(--accent-a3)",
            "color": "var(--accent-a11)",
        },
    ]


def test_avatar_image_over_the_fallback(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The image lies over the fallback, and its ref says how its load ended."""
    component = rx.ui.avatar(
        src="/ada.png",
        alt="Ada",
        fallback="A",
        size="5",
        variant="solid",
        high_contrast=True,
        radius="full",
        id="ada",
    )
    assert component.render() == {
        "name": '"span"',
        "props": [
            'className:sx_119fa60175_c + " " + reflexUIClasses_4c7cd6a7ce',
            'id:"ada"',
            "ref:ref_ada",
        ],
        "children": [
            {
                "name": '"span"',
                "props": ["className:sx_a4a6b79df8_c"],
                "children": [{"contents": '"A"'}],
            },
            {
                "name": '"img"',
                "props": [
                    'alt:"Ada"',
                    "className:sx_b22e24c3d6_c",
                    "ref:watchImage",
                    'src:"/ada.png"',
                ],
                "children": [],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "middle",
            "userSelect": "none",
            "width": "var(--avatar-size)",
            "height": "var(--avatar-size)",
            "flexShrink": 0,
            "--avatar-size": "var(--space-9)",
            "--avatar-fallback-one-letter-font-size": "var(--font-size-6)",
            "borderRadius": "max(var(--radius-4), var(--radius-full))",
            "letterSpacing": "var(--letter-spacing-6)",
        },
        {
            "boxSizing": "border-box",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-medium)",
            "fontStyle": "normal",
            "zIndex": 0,
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "lineHeight": 1,
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "textTransform": "uppercase",
            "flexShrink": 0,
            "visibility": {"[data-status='loaded']": "hidden"},
            "fontSize": "var(--avatar-fallback-one-letter-font-size)",
            "backgroundColor": "var(--accent-12)",
            "color": "var(--accent-1)",
        },
        {
            "boxSizing": "border-box",
            "display": {"default": "block", "[data-status='error']": "none"},
            "maxWidth": "100%",
            "width": "100%",
            "height": "100%",
            "objectFit": "cover",
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "flexShrink": 0,
            "marginLeft": "-100%",
        },
    ]


def test_avatar_fallback_bound_to_state(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A fallback bound to state has the size of the text around it."""
    component = rx.ui.avatar(
        fallback=AvatarState.initials, size=rx.breakpoints(initial="1", md="4")
    )
    assert component.render() == {
        "name": '"span"',
        "props": ["className:sx_0c15401e7f_c"],
        "children": [
            {
                "name": '"span"',
                "props": ["className:sx_5204d15c1d_c"],
                "children": [
                    {
                        "contents": "reflex___state____state__tests___units___reflex_components_ui___components___test_avatar____avatar_state.initials_rx_state_"
                    }
                ],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "boxSizing": "border-box",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "verticalAlign": "middle",
            "userSelect": "none",
            "width": "var(--avatar-size)",
            "height": "var(--avatar-size)",
            "flexShrink": 0,
            "--avatar-size": {
                "default": "var(--space-5)",
                "@media (min-width: 1024px)": "var(--space-8)",
            },
            "--avatar-fallback-one-letter-font-size": {
                "default": "var(--font-size-2)",
                "@media (min-width: 1024px)": "var(--font-size-5)",
            },
            "borderRadius": {
                "default": "max(var(--radius-2), var(--radius-full))",
                "@media (min-width: 1024px)": "max(var(--radius-3), "
                "var(--radius-full))",
            },
            "letterSpacing": {
                "default": "var(--letter-spacing-1)",
                "@media (min-width: 1024px)": "var(--letter-spacing-4)",
            },
            "--avatar-fallback-two-letters-font-size": {
                "default": "var(--font-size-1)",
                "@media (min-width: 1024px)": "var(--font-size-4)",
            },
        },
        {
            "boxSizing": "border-box",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-medium)",
            "fontStyle": "normal",
            "zIndex": 0,
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "lineHeight": 1,
            "borderTopLeftRadius": "inherit",
            "borderTopRightRadius": "inherit",
            "borderBottomRightRadius": "inherit",
            "borderBottomLeftRadius": "inherit",
            "textTransform": "uppercase",
            "flexShrink": 0,
            "visibility": {"[data-status='loaded']": "hidden"},
            "backgroundColor": "var(--accent-a3)",
            "color": "var(--accent-a11)",
        },
    ]


def test_avatar_imports_its_script_only_with_an_image(ui_plugin: UIPlugin):
    """The one script of an avatar follows the load of an image."""
    script = "$/reflex-ui/behaviors/image-status.js"
    assert script not in rx.ui.avatar(fallback="AB")._get_all_imports()
    assert rx.ui.avatar(src="/ada.png", fallback="AB")._get_all_imports()[script] == [
        ImportVar(tag="watchImage")
    ]
