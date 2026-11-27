"""Tests for reflex_components_ui.components.progress."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.vars.base import Var
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError, keyframes

import reflex as rx

WAITING = "[data-state='indeterminate']"

GROW = {
    "0%": {"transform": "scaleX(0.01)"},
    "20%": {"transform": "scaleX(0.1)"},
    "30%": {"transform": "scaleX(0.6)"},
    "40%": {"transform": "scaleX(0.9)"},
    "50%": {"transform": "scaleX(0.9)"},
    "100%": {"transform": "scaleX(1)"},
}
SHINE = keyframes({
    "0%": {"transform": "translateX(-100%)"},
    "100%": {"transform": "translateX(0%)"},
})
SHINE_IMAGE = (
    "linear-gradient(to right, transparent 25%, "
    "var(--rx-if-light, var(--white-a5), var(--white-a9), var(--white-a5)) "
    "var(--rx-if-dark, var(--white-a3), var(--white-a6), var(--white-a3)), "
    "transparent 75%)"
)


class ProgressState(rx.State):
    """State a progress bar is bound to."""

    done: rx.Field[int] = rx.field(3)
    total: rx.Field[int] = rx.field(10)


DONE = str(ProgressState.done)
TOTAL = str(ProgressState.total)


def track(**changed: Any) -> dict[str, Any]:
    """Describe the style a progress bar declares.

    Args:
        **changed: The properties that are not those of a plain bar, None for
            one a bar does not set.

    Returns:
        The whole style of a surface bar of size 2, with the changes.
    """
    style = {
        "--progress-value": "0",
        "--progress-max": "100",
        "--progress-duration": "5s",
        "boxSizing": {"default": "border-box", "::after": "border-box"},
        "pointerEvents": "none",
        "position": {"default": "relative", "::after": "absolute"},
        "overflowX": "hidden",
        "overflowY": "hidden",
        "flexGrow": 1,
        "height": "var(--progress-height)",
        "borderRadius": (
            "max(calc(var(--radius-factor) * var(--progress-height) / 3), "
            "calc(var(--radius-factor) * var(--radius-thumb)))"
        ),
        "top": {"::after": "0"},
        "right": {"::after": "0"},
        "bottom": {"::after": "0"},
        "left": {"::after": "0"},
        "content": {"::after": "''"},
        "borderTopLeftRadius": {"::after": "inherit"},
        "borderTopRightRadius": {"::after": "inherit"},
        "borderBottomRightRadius": {"::after": "inherit"},
        "borderBottomLeftRadius": {"::after": "inherit"},
        "--progress-height": "calc(var(--space-2) * 0.75)",
        "backgroundColor": "var(--gray-a3)",
        "boxShadow": {"::after": "inset 0 0 0 1px var(--gray-a4)"},
        "width": "100%",
        **changed,
    }
    return {prop: value for prop, value in style.items() if value is not None}


def indicator(
    color: str = "var(--accent-track)",
    faded: dict[str, Any] | None = None,
    back: dict[str, Any] | None = None,
    **changed: Any,
) -> dict[str, Any]:
    """Describe the style the indicator of a progress bar declares.

    Args:
        color: The color of the variant.
        faded: What the indicator fades to while it waits.
        back: What it pulses back to.
        **changed: The properties that are not those of a surface indicator.

    Returns:
        The whole style.
    """
    faded = faded or {"background_color": "var(--accent-7)"}
    back = back or {"background_color": "var(--accent-track)"}
    return {
        "boxSizing": {"default": "border-box", "::after": {WAITING: "border-box"}},
        "display": "block",
        "height": "100%",
        "width": {"default": "100%", "::after": {WAITING: "400%"}},
        "transform": "scaleX(calc(var(--progress-value) / var(--progress-max)))",
        "transformOrigin": "left center",
        "transitionProperty": "transform",
        "transitionDuration": "120ms",
        "animationDelay": {
            WAITING: (
                "0s, calc(var(--progress-duration) + 5s), "
                "calc(var(--progress-duration) + 7.5s)"
            ),
            "::after": {WAITING: "calc(var(--progress-duration) + 5s)"},
        },
        "animationDuration": {
            WAITING: "var(--progress-duration), 2.5s, 5s",
            "::after": {WAITING: "5s"},
        },
        "animationIterationCount": {
            WAITING: "1, 1, infinite",
            "::after": {WAITING: "infinite"},
        },
        "animationFillMode": {
            WAITING: "both, none, none",
            "::after": {WAITING: "backwards"},
        },
        "animationDirection": {WAITING: "normal, normal, alternate"},
        "position": {"::after": {WAITING: "absolute"}},
        "top": {"::after": {WAITING: "0"}},
        "right": {"::after": {WAITING: "0"}},
        "bottom": {"::after": {WAITING: "0"}},
        "left": {"::after": {WAITING: "0"}},
        "content": {"::after": {WAITING: "''"}},
        "animationName": {
            "::after": {WAITING: SHINE},
            WAITING: keyframes(GROW, {"100%": faded}, {"0%": faded, "100%": back}),
        },
        "backgroundImage": {"::after": {WAITING: SHINE_IMAGE}},
        "backgroundColor": f"var(--rx-progress-fill, {color})",
        **changed,
    }


def test_progress_with_a_value(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A bar says how far it is to assistive technology and to its indicator."""
    component = rx.ui.progress(value=25)
    assert component.render() == {
        "name": '"div"',
        "props": [
            '"aria-valuemax":100',
            '"aria-valuemin":0',
            '"aria-valuenow":25',
            '"aria-valuetext":"25%"',
            "className:sx_3f4f92d33a_c",
            '"data-max":100',
            '"data-state":"loading"',
            '"data-value":25',
            'role:"progressbar"',
        ],
        "children": [
            {
                "name": '"div"',
                "props": [
                    "className:sx_0fd9549b4f_c",
                    '"data-max":100',
                    '"data-state":"loading"',
                    '"data-value":25',
                ],
                "children": [],
            }
        ],
    }
    assert declared_styles(component) == [
        track(**{"--progress-value": "25"}),
        indicator(),
    ]


def test_progress_without_a_value(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A bar without a value waits for as long as its duration, in the look of its props."""
    component = rx.ui.progress(
        variant="soft",
        size="3",
        high_contrast=True,
        color_scheme="ruby",
        radius="full",
        duration="10s",
        fill_color="red",
        width="50%",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            '"aria-valuemax":100',
            '"aria-valuemin":0',
            (
                'className:sx_635f52cf10_c + " " + reflexUIClasses_e201574881 + " " + '
                "reflexUIClasses_4c7cd6a7ce"
            ),
            '"data-max":100',
            '"data-state":"indeterminate"',
            'role:"progressbar"',
        ],
        "children": [
            {
                "name": '"div"',
                "props": [
                    "className:sx_3ba578a75b_c",
                    '"data-max":100',
                    '"data-state":"indeterminate"',
                ],
                "children": [],
            }
        ],
    }
    waiting = indicator(
        "var(--accent-12)",
        {"opacity": 0.8},
        {"opacity": 1},
        opacity={"::after": {WAITING: 0.75}},
    )
    waiting["backgroundImage"] = {
        "default": "linear-gradient(var(--accent-a5), var(--accent-a5))",
        "::after": {WAITING: SHINE_IMAGE},
    }
    styles = declared_styles(component)
    assert styles == [
        track(**{
            "--progress-duration": "10s",
            "--progress-height": "var(--space-2)",
            "backgroundColor": "var(--gray-a4)",
            "backgroundImage": "linear-gradient(var(--white-a1), var(--white-a1))",
            "boxShadow": None,
            "--rx-accent-text": "var(--accent-12)",
            "--rx-accent-link": "var(--accent-12)",
            "--rx-accent-link-line": "underline",
            "--rx-accent-link-line-color": (
                "color-mix(in oklab, var(--accent-a6), var(--gray-a6))"
            ),
            "width": "50%",
            "--rx-progress-fill": "red",
        }),
        waiting,
    ]


def test_progress_bound_to_state(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A value bound to state is a custom property, and is checked in the browser."""
    component = rx.ui.progress(value=ProgressState.done, max=ProgressState.total)
    limit = f'(typeof {TOTAL} === "number" && {TOTAL} > 0 ? {TOTAL} : 100)'
    valid = f'typeof {DONE} === "number" && {DONE} >= 0 && {DONE} <= {limit}'
    now = f"({valid} ? {DONE} : undefined)"
    state = (
        f'({valid} ? ({DONE} === {limit} ? "complete" : "loading") : "indeterminate")'
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            f'"aria-valuemax":{limit}',
            '"aria-valuemin":0',
            f'"aria-valuenow":{now}',
            (
                f'"aria-valuetext":({valid} ? Math.round({DONE} / {limit} * 100) + "%" '
                ": undefined)"
            ),
            "className:sx_3453e4362e_c",
            f'"data-max":{limit}',
            f'"data-state":{state}',
            f'"data-value":{now}',
            'role:"progressbar"',
            f'style:({{ "--v0": ({DONE}) ?? "initial", "--v1": ({TOTAL}) ?? "initial" }})',
        ],
        "children": [
            {
                "name": '"div"',
                "props": [
                    "className:sx_0fd9549b4f_c",
                    f'"data-max":{limit}',
                    f'"data-state":{state}',
                    f'"data-value":{now}',
                ],
                "children": [],
            }
        ],
    }
    root, inner = declared_styles(component)
    assert {
        prop: str(value) if isinstance(value, Var) else value
        for prop, value in root.items()
    } == track(**{"--progress-value": DONE, "--progress-max": TOTAL})
    assert inner == indicator()


def test_progress_checks_its_value_as_radix_does(
    ui_plugin: UIPlugin, declared_styles: Callable[[Any], list[dict[str, Any]]]
):
    """A value over the maximum is no value, and a maximum of zero is 100."""
    component = rx.ui.progress(value=150, max=0, aria_valuetext="unknown")
    assert component.render() == {
        "name": '"div"',
        "props": [
            '"aria-valuemax":100',
            '"aria-valuemin":0',
            '"aria-valuetext":"unknown"',
            "className:sx_6d82c8dfbb_c",
            '"data-max":100',
            '"data-state":"indeterminate"',
            'role:"progressbar"',
        ],
        "children": [
            {
                "name": '"div"',
                "props": [
                    "className:sx_0fd9549b4f_c",
                    '"data-max":100',
                    '"data-state":"indeterminate"',
                ],
                "children": [],
            }
        ],
    }
    assert declared_styles(component) == [
        track(**{"--progress-value": "150", "--progress-max": "0"}),
        indicator(),
    ]
    complete = rx.ui.progress(value=8, max=8).render()
    assert complete["props"] == [
        '"aria-valuemax":8',
        '"aria-valuemin":0',
        '"aria-valuenow":8',
        '"aria-valuetext":"100%"',
        "className:sx_68b5d1fe7c_c",
        '"data-max":8',
        '"data-state":"complete"',
        '"data-value":8',
        'role:"progressbar"',
    ]


def test_progress_rejects_an_unknown_variant(ui_plugin: UIPlugin):
    with pytest.raises(StyleError) as error:
        rx.ui.progress(variant="solid")  # pyright: ignore[reportArgumentType]
    assert str(error.value) == (
        'rx.ui.progress: unknown variant "solid". The values are "classic", '
        '"surface", "soft".'
    )
