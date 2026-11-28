"""Tests for reflex_components_ui.components.text_area."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


class AreaState(rx.State):
    """What a text area is bound to."""

    text: str = ""

    @rx.event
    def set_text(self, text: str):
        """Follow the text area.

        Args:
            text: Its text.
        """
        self.text = text


def test_text_area(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A text area is a box around a native textarea: its attributes, its id and its events are the ones of the textarea, and its styles the ones of the box."""
    component = rx.ui.text_area(
        placeholder="Notes",
        id="notes",
        name="notes",
        rows="3",
        margin="1px",
        class_name="mine",
        on_blur=AreaState.set_text,
        aria_label="Notes",
    )
    assert component.render() == {
        "name": '"div"',
        "props": ['className:"mine " + sx_a60f107124_c'],
        "children": [
            {
                "name": '"textarea"',
                "props": [
                    '"aria-label":"Notes"',
                    "className:sx_8eecb42f44_c",
                    '"data-rx-text-area-input":""',
                    'id:"notes"',
                    'name:"notes"',
                    'onBlur:((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_text_area____area_state.set_text", ({ ["text"] : _e?.["target"]?.["value"] }), ({  })))], [_e], ({  }))))',
                    'placeholder:"Notes"',
                    "ref:ref_notes",
                    'rows:"3"',
                ],
                "children": [],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "display": "flex",
            "flexDirection": "column",
            "boxSizing": "border-box",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "overflowX": "hidden",
            "overflowY": "hidden",
            "padding": "var(--text-area-border-width)",
            "outlineWidth": {":focus-within": "2px"},
            "outlineStyle": {":focus-within": "solid"},
            "outlineOffset": {":focus-within": "-1px"},
            "minHeight": "var(--space-9)",
            "borderTopLeftRadius": "var(--radius-2)",
            "borderTopRightRadius": "var(--radius-2)",
            "borderBottomRightRadius": "var(--radius-2)",
            "borderBottomLeftRadius": "var(--radius-2)",
            "--text-area-border-width": "1px",
            "backgroundClip": "content-box",
            "backgroundColor": "var(--color-surface)",
            "backgroundImage": {
                ":has(> :is(input, textarea):autofill:not(:is(:disabled, :read-only)))": "linear-gradient(var(--focus-a2), var(--focus-a2))",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "linear-gradient(var(--gray-a2), var(--gray-a2))",
            },
            "boxShadow": {
                "default": "inset 0 0 0 var(--text-area-border-width) var(--gray-a7)",
                ":has(> :is(input, textarea):autofill:not(:is(:disabled, :read-only)))": "inset 0 0 0 1px var(--focus-a5), inset 0 0 0 1px var(--gray-a5)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "inset 0 0 0 var(--text-area-border-width) var(--gray-a6)",
            },
            "color": "var(--gray-12)",
            "outlineColor": {
                ":focus-within:not(:has(> :is(input, textarea):is(:disabled, :read-only)))": "var(--focus-8)",
                ":focus-within:has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-8)",
            },
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
        },
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderRightWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderBottomWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderLeftWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderTopStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "borderRightStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "borderBottomStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "borderLeftStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "backgroundColor": {
                "default": "transparent",
                "::-webkit-scrollbar-track": "var(--gray-a3)",
                "::-webkit-scrollbar-thumb": "var(--gray-a8)",
                "::selection": {":is(:disabled, :read-only)": "var(--gray-a5)"},
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": {
                "default": "inherit",
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                "::placeholder": "var(--gray-a10)",
            },
            "fontFamily": "inherit",
            "fontSize": "var(--font-size-2)",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "lineHeight": "var(--line-height-2)",
            "letterSpacing": "var(--letter-spacing-2)",
            "textTransform": "inherit",
            "wordSpacing": "inherit",
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "whiteSpace": "pre-wrap",
            "WebkitTapHighlightColor": "transparent",
            "borderTopLeftRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "borderTopRightRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "borderBottomRightRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "borderBottomLeftRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "resize": "none",
            "display": "block",
            "width": {"default": "100%", "::-webkit-scrollbar": "var(--space-3)"},
            "flexGrow": 1,
            "textAlign": "start",
            "textIndent": "initial",
            "padding": "var(--text-area-padding-y) var(--text-area-padding-x)",
            "cursor": {
                "default": "auto",
                ":is(:disabled, :read-only):not(:placeholder-shown)": "text",
                ":is(:disabled, :read-only):placeholder-shown": "var(--cursor-disabled)",
            },
            "WebkitTextFillColor": {
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                ":autofill": "var(--gray-12)",
            },
            "backgroundClip": {
                ":autofill": "text",
                "::-webkit-scrollbar-track": "content-box",
                "::-webkit-scrollbar-thumb": "content-box",
            },
            "height": {"::-webkit-scrollbar": "var(--space-3)"},
            "borderTopColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "borderRightColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "borderBottomColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "borderLeftColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "--text-area-padding-y": "calc(var(--space-1) * 1.5 - var(--text-area-border-width))",
            "--text-area-padding-x": "calc(var(--space-2) - var(--text-area-border-width))",
            "userSelect": {"::placeholder": "none"},
            "opacity": {
                "::placeholder": {"default": 1, ":is(:disabled, :read-only)": 0.5}
            },
        },
    ]


def test_text_area_soft(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """The size and the variant reach the textarea, a padding is the one of the textarea, and the box is what resizes."""
    component = rx.ui.text_area(
        size="3",
        variant="soft",
        color_scheme="ruby",
        radius="large",
        resize=rx.breakpoints(initial="none", md="both"),
        padding="2px",
        disabled=True,
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            'className:sx_7ad8a315b7_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_1df0c09a3a'
        ],
        "children": [
            {
                "name": '"textarea"',
                "props": [
                    "className:sx_9c17918843_c",
                    '"data-rx-text-area-input":""',
                    "disabled:true",
                ],
                "children": [],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "display": "flex",
            "flexDirection": "column",
            "boxSizing": "border-box",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "overflowX": "hidden",
            "overflowY": "hidden",
            "padding": "var(--text-area-border-width)",
            "outlineWidth": {":focus-within": "2px"},
            "outlineStyle": {":focus-within": "solid"},
            "outlineOffset": {":focus-within": "-1px"},
            "minHeight": "80px",
            "borderTopLeftRadius": "var(--radius-3)",
            "borderTopRightRadius": "var(--radius-3)",
            "borderBottomRightRadius": "var(--radius-3)",
            "borderBottomLeftRadius": "var(--radius-3)",
            "--text-area-border-width": "0px",
            "backgroundColor": {
                "default": "var(--accent-a3)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-a3)",
            },
            "boxShadow": {
                ":has(> :is(input, textarea):autofill:not(:is(:disabled, :read-only)))": "inset 0 0 0 1px var(--accent-a5), inset 0 0 0 1px var(--gray-a4)"
            },
            "color": "var(--accent-12)",
            "outlineColor": {
                ":focus-within:not(:has(> :is(input, textarea):is(:disabled, :read-only)))": "var(--accent-8)",
                ":focus-within:has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-8)",
            },
            "resize": {"default": "none", "@media (min-width: 1024px)": "both"},
        },
        {
            "appearance": "none",
            "marginTop": "0",
            "marginRight": "0",
            "marginBottom": "0",
            "marginLeft": "0",
            "borderTopWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderRightWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderBottomWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderLeftWidth": {
                "default": "0",
                "::-webkit-scrollbar-track": "var(--space-1)",
                "::-webkit-scrollbar-thumb": "var(--space-1)",
            },
            "borderTopStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "borderRightStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "borderBottomStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "borderLeftStyle": {
                "default": "none",
                "::-webkit-scrollbar-track": "solid",
                "::-webkit-scrollbar-thumb": "solid",
            },
            "backgroundColor": {
                "default": "transparent",
                "::-webkit-scrollbar-track": "var(--gray-a3)",
                "::-webkit-scrollbar-thumb": "var(--gray-a8)",
                "::selection": {
                    "default": "var(--accent-a5)",
                    ":is(:disabled, :read-only)": "var(--gray-a5)",
                },
            },
            "backgroundImage": "none",
            "boxSizing": "border-box",
            "color": {
                "default": "inherit",
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                "::placeholder": "var(--accent-12)",
            },
            "fontFamily": "inherit",
            "fontSize": "var(--font-size-3)",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "lineHeight": "var(--line-height-3)",
            "letterSpacing": "var(--letter-spacing-3)",
            "textTransform": "inherit",
            "wordSpacing": "inherit",
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "whiteSpace": "pre-wrap",
            "WebkitTapHighlightColor": "transparent",
            "borderTopLeftRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "borderTopRightRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "borderBottomRightRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "borderBottomLeftRadius": {
                "default": "inherit",
                "::-webkit-scrollbar-track": "var(--space-3)",
                "::-webkit-scrollbar-thumb": "var(--space-3)",
            },
            "resize": "none",
            "display": "block",
            "width": {"default": "100%", "::-webkit-scrollbar": "var(--space-3)"},
            "flexGrow": 1,
            "textAlign": "start",
            "textIndent": "initial",
            "padding": "var(--text-area-padding-y) var(--text-area-padding-x)",
            "cursor": {
                "default": "auto",
                ":is(:disabled, :read-only):not(:placeholder-shown)": "text",
                ":is(:disabled, :read-only):placeholder-shown": "var(--cursor-disabled)",
            },
            "WebkitTextFillColor": {
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                ":autofill": "var(--gray-12)",
            },
            "backgroundClip": {
                ":autofill": "text",
                "::-webkit-scrollbar-track": "content-box",
                "::-webkit-scrollbar-thumb": "content-box",
            },
            "height": {"::-webkit-scrollbar": "var(--space-3)"},
            "borderTopColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "borderRightColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "borderBottomColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "borderLeftColor": {
                "::-webkit-scrollbar-track": "transparent",
                "::-webkit-scrollbar-thumb": "transparent",
            },
            "--text-area-padding-y": "calc(var(--space-2) - var(--text-area-border-width))",
            "--text-area-padding-x": "calc(var(--space-3) - var(--text-area-border-width))",
            "userSelect": {"::placeholder": "none"},
            "opacity": {
                "::placeholder": {"default": 0.65, ":is(:disabled, :read-only)": 0.5}
            },
            "paddingTop": "2px",
            "paddingRight": "2px",
            "paddingBottom": "2px",
            "paddingLeft": "2px",
        },
    ]


def test_text_area_bound_to_state(
    ui_plugin: UIPlugin,
):
    """A textarea a state controls is wrapped to keep what is typed, with the class names of its styles."""
    component = rx.ui.text_area(
        value=AreaState.text, on_change=AreaState.set_text, id="bound"
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_246a7bce17_c"],
        "children": [
            {
                "name": "DebounceInput",
                "props": [
                    "className:sx_8eecb42f44_c",
                    '"data-rx-text-area-input":""',
                    "debounceTimeout:300",
                    'element:"textarea"',
                    'id:"bound"',
                    "inputRef:ref_bound",
                    'onChange:((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_text_area____area_state.set_text", ({ ["text"] : _e?.["target"]?.["value"] }), ({  })))], [_e], ({  }))))',
                    "value:reflex___state____state__tests___units___reflex_components_ui___components___test_text_area____area_state.text_rx_state_",
                ],
                "children": [],
            }
        ],
    }


def test_text_area_unknown_resize(ui_plugin: UIPlugin):
    """A resize behavior a text area does not have is an error that lists the ones it has."""
    with pytest.raises(StyleError) as error:
        rx.ui.text_area(resize="diagonal")
    assert (
        str(error.value)
        == 'rx.ui.text_area: unknown resize "diagonal". The values are "none", "vertical", "horizontal", "both".'
    )
