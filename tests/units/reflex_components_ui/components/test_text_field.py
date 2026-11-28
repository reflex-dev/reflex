"""Tests for reflex_components_ui.components.text_field."""

from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import StyleError

import reflex as rx


class FieldState(rx.State):
    """What a text field is bound to."""

    text: str = ""
    maybe: str | None = None
    complete: bool = True

    @rx.event
    def set_text(self, text: str):
        """Follow the field.

        Args:
            text: Its text.
        """
        self.text = text


def test_text_field(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A text field is a box around a native input: its attributes, its id and its events are the ones of the input, and its styles the ones of the box."""
    component = rx.ui.input(
        placeholder="Search",
        id="q",
        name="q",
        max_length=5,
        margin="1px",
        class_name="mine",
        on_blur=FieldState.set_text,
        auto_complete=True,  # pyright: ignore[reportArgumentType]
        aria_label="Query",
        spell_check=True,
    )
    assert component.render() == {
        "name": '"div"',
        "props": ['className:"mine " + sx_9bc77afb58_c'],
        "children": [
            {
                "name": '"input"',
                "props": [
                    '"aria-label":"Query"',
                    'autoComplete:"on"',
                    "className:sx_345c25de08_c",
                    '"data-rx-text-field-input":""',
                    'id:"q"',
                    "maxLength:5",
                    'name:"q"',
                    'onBlur:((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_text_field____field_state.set_text", ({ ["text"] : _e?.["target"]?.["value"] }), ({  })))], [_e], ({  }))))',
                    'placeholder:"Search"',
                    "ref:ref_q",
                    "spellCheck:true",
                ],
                "children": [],
            }
        ],
    }
    assert declared_styles(component) == [
        {
            "display": {
                "default": "flex",
                ":has(> input:is([hidden], [type='hidden' i]))": "none",
            },
            "alignItems": "stretch",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "boxSizing": "border-box",
            "height": "var(--text-field-height)",
            "padding": "var(--text-field-border-width)",
            "borderRadius": "var(--text-field-border-radius)",
            "outlineWidth": {":has(> :is(input, textarea):focus)": "2px"},
            "outlineStyle": {":has(> :is(input, textarea):focus)": "solid"},
            "outlineColor": {
                ":has(> :is(input, textarea):focus)": "var(--text-field-focus-color)"
            },
            "outlineOffset": {":has(> :is(input, textarea):focus)": "-1px"},
            "backgroundColor": {
                "default": "var(--color-surface)",
                "::selection": "var(--text-field-selection-color)",
            },
            "--rx-text-field-indent": {
                "default": "var(--text-field-padding)",
                ":has(> [data-side='left'])": "0",
            },
            "--rx-text-field-padding-left": {
                "default": "var(--text-field-padding)",
                ":has(> [data-side='left'])": "0",
            },
            "--rx-text-field-padding-right": {
                "default": "var(--text-field-padding)",
                ":has(> [data-side='right'])": "0",
            },
            "--rx-text-field-radius-left": {
                "default": "calc(var(--text-field-border-radius) - var(--text-field-border-width))",
                ":has(> [data-side='left'])": "0",
            },
            "--rx-text-field-radius-right": {
                "default": "calc(var(--text-field-border-radius) - var(--text-field-border-width))",
                ":has(> [data-side='right'])": "0",
            },
            "--rx-text-field-slot-cursor": {
                "default": "text",
                ":has(> :is(input, textarea):is(:disabled, :read-only):placeholder-shown)": "var(--cursor-disabled)",
            },
            "--text-field-height": "var(--space-6)",
            "--text-field-padding": "calc(var(--space-2) - var(--text-field-border-width))",
            "--text-field-border-radius": "max(var(--radius-2), var(--radius-full))",
            "--text-field-native-icon-size": "var(--space-4)",
            "fontSize": "var(--font-size-2)",
            "letterSpacing": "var(--letter-spacing-2)",
            "--rx-text-field-slot-gap": "var(--space-2)",
            "--rx-text-field-slot-padding": "var(--space-2)",
            "--text-field-selection-color": {
                "default": "var(--focus-a5)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-a5)",
            },
            "--text-field-focus-color": {
                "default": "var(--focus-8)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-8)",
            },
            "--text-field-border-width": "1px",
            "color": "var(--gray-12)",
            "--rx-text-field-slot-color": "var(--gray-a11)",
            "boxShadow": {
                "default": "inset 0 0 0 var(--text-field-border-width) var(--gray-a7)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "inset 0 0 0 var(--text-field-border-width) var(--gray-a6)",
                ":has(> :is(input, textarea):autofill:not(:is(:disabled, :read-only)))": "inset 0 0 0 1px var(--focus-a5), inset 0 0 0 1px var(--gray-a5)",
            },
            "backgroundImage": {
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "linear-gradient(var(--gray-a2), var(--gray-a2))",
                ":has(> :is(input, textarea):autofill:not(:is(:disabled, :read-only)))": "linear-gradient(var(--focus-a2), var(--focus-a2))",
            },
            "backgroundClip": "content-box",
            "marginTop": "1px",
            "marginRight": "1px",
            "marginBottom": "1px",
            "marginLeft": "1px",
        },
        {
            "appearance": {
                "default": "none",
                "[type='number']": "textfield",
                "::-webkit-inner-spin-button": "none",
                "::-webkit-search-cancel-button": "none",
            },
            "marginTop": "0",
            "marginRight": {
                "default": "0",
                "::-webkit-calendar-picker-indicator": "calc(var(--space-1) * -1)",
            },
            "marginBottom": "0",
            "marginLeft": {
                "default": "0",
                "::-webkit-calendar-picker-indicator": {
                    "default": "var(--space-1)",
                    "[type='time']": "0",
                },
            },
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
                "::selection": "var(--text-field-selection-color)",
            },
            "backgroundImage": "none",
            "boxSizing": {
                "default": "border-box",
                "::-webkit-calendar-picker-indicator": "content-box",
            },
            "color": {
                "default": "inherit",
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                "::placeholder": "var(--gray-a10)",
            },
            "fontFamily": "inherit",
            "fontSize": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "textTransform": "inherit",
            "wordSpacing": "inherit",
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "whiteSpace": "pre-wrap",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "text",
                ":is(:disabled, :read-only):placeholder-shown": "var(--cursor-disabled)",
            },
            "WebkitTextFillColor": {
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                ":autofill": "var(--gray-12)",
            },
            "width": {
                "default": "100%",
                "::-webkit-calendar-picker-indicator": "var(--text-field-native-icon-size)",
            },
            "display": "flex",
            "alignItems": "center",
            "textAlign": "inherit",
            "borderRadius": {
                "::-webkit-calendar-picker-indicator": "calc(var(--text-field-border-radius) - 2px)"
            },
            "borderTopLeftRadius": "var(--rx-text-field-radius-left)",
            "borderBottomLeftRadius": "var(--rx-text-field-radius-left)",
            "borderTopRightRadius": "var(--rx-text-field-radius-right)",
            "borderBottomRightRadius": "var(--rx-text-field-radius-right)",
            "textIndent": {
                "default": "var(--rx-text-field-indent)",
                ":is([type='date'], [type='datetime-local'], [type='time'], [type='week'], [type='month'])": "0",
            },
            "paddingTop": {
                "default": "0",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "paddingLeft": {
                "default": "0",
                ":is([type='date'], [type='datetime-local'], [type='time'], [type='week'], [type='month'])": "var(--rx-text-field-padding-left)",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "paddingRight": {
                "default": "0",
                ":is([type='date'], [type='datetime-local'], [type='time'], [type='week'], [type='month'])": "var(--rx-text-field-padding-right)",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "height": {
                "::-webkit-calendar-picker-indicator": "var(--text-field-native-icon-size)"
            },
            "paddingBottom": {
                "default": "0.5px",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "backgroundClip": {":autofill": "text"},
            "userSelect": {"::placeholder": "none"},
            "opacity": {
                "::placeholder": {"default": 1, ":is(:disabled, :read-only)": 0.5}
            },
        },
    ]


def test_text_field_with_slots(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A slot is on the side it names; the first without one is on the left and the next on the right, and a pointer on either gives the input the focus."""
    component = rx.ui.input(
        rx.ui.input.slot("a"),
        rx.ui.input.slot("b"),
        rx.ui.input.slot("c", side="left", color_scheme="ruby"),
        size="3",
        variant="soft",
        color_scheme="ruby",
        radius="full",
        type="date",
    )
    assert component.render() == {
        "name": '"div"',
        "props": [
            'className:sx_59632c79fd_c + " " + reflexUIClasses_e201574881 + " " + reflexUIClasses_4c7cd6a7ce',
            "onPointerDown:focusField",
        ],
        "children": [
            {
                "name": '"input"',
                "props": [
                    "className:sx_d1160bcc70_c",
                    '"data-rx-text-field-input":""',
                    "spellCheck:false",
                    'type:"date"',
                ],
                "children": [],
            },
            {
                "name": '"div"',
                "props": ["className:sx_85d7cf39b6_c", '"data-side":"left"'],
                "children": [{"contents": '"a"'}],
            },
            {
                "name": '"div"',
                "props": ["className:sx_836caf5117_c", '"data-side":"right"'],
                "children": [{"contents": '"b"'}],
            },
            {
                "name": '"div"',
                "props": [
                    'className:sx_b7c64f6b9b_c + " " + reflexUIClasses_e201574881',
                    '"data-side":"left"',
                ],
                "children": [{"contents": '"c"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {
            "display": {
                "default": "flex",
                ":has(> input:is([hidden], [type='hidden' i]))": "none",
            },
            "alignItems": "stretch",
            "fontFamily": "var(--default-font-family)",
            "fontWeight": "var(--font-weight-regular)",
            "fontStyle": "normal",
            "textAlign": "start",
            "boxSizing": "border-box",
            "height": "var(--text-field-height)",
            "padding": "var(--text-field-border-width)",
            "borderRadius": "var(--text-field-border-radius)",
            "outlineWidth": {":has(> :is(input, textarea):focus)": "2px"},
            "outlineStyle": {":has(> :is(input, textarea):focus)": "solid"},
            "outlineColor": {
                ":has(> :is(input, textarea):focus)": "var(--text-field-focus-color)"
            },
            "outlineOffset": {":has(> :is(input, textarea):focus)": "-1px"},
            "backgroundColor": {
                "default": "var(--accent-a3)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-a3)",
                "::selection": "var(--text-field-selection-color)",
            },
            "--rx-text-field-indent": {
                "default": "var(--text-field-padding)",
                ":has(> [data-side='left'])": "0",
            },
            "--rx-text-field-padding-left": {
                "default": "var(--text-field-padding)",
                ":has(> [data-side='left'])": "0",
            },
            "--rx-text-field-padding-right": {
                "default": "var(--text-field-padding)",
                ":has(> [data-side='right'])": "0",
            },
            "--rx-text-field-radius-left": {
                "default": "calc(var(--text-field-border-radius) - var(--text-field-border-width))",
                ":has(> [data-side='left'])": "0",
            },
            "--rx-text-field-radius-right": {
                "default": "calc(var(--text-field-border-radius) - var(--text-field-border-width))",
                ":has(> [data-side='right'])": "0",
            },
            "--rx-text-field-slot-cursor": {
                "default": "text",
                ":has(> :is(input, textarea):is(:disabled, :read-only):placeholder-shown)": "var(--cursor-disabled)",
            },
            "--text-field-height": "var(--space-7)",
            "--text-field-padding": "calc(var(--space-3) - var(--text-field-border-width))",
            "--text-field-border-radius": "max(var(--radius-3), var(--radius-full))",
            "--text-field-native-icon-size": "var(--space-4)",
            "fontSize": "var(--font-size-3)",
            "letterSpacing": "var(--letter-spacing-3)",
            "--rx-text-field-slot-gap": "var(--space-3)",
            "--rx-text-field-slot-padding": "var(--space-3)",
            "--text-field-selection-color": {
                "default": "var(--accent-a5)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-a5)",
            },
            "--text-field-focus-color": {
                "default": "var(--accent-8)",
                ":has(> :is(input, textarea):is(:disabled, :read-only))": "var(--gray-8)",
            },
            "--text-field-border-width": "0px",
            "color": "var(--accent-12)",
            "--rx-text-field-slot-color": "var(--accent-12)",
            "boxShadow": {
                ":has(> :is(input, textarea):autofill:not(:is(:disabled, :read-only)))": "inset 0 0 0 1px var(--accent-a5), inset 0 0 0 1px var(--gray-a4)"
            },
        },
        {
            "appearance": {
                "default": "none",
                "[type='number']": "textfield",
                "::-webkit-inner-spin-button": "none",
                "::-webkit-search-cancel-button": "none",
            },
            "marginTop": "0",
            "marginRight": {
                "default": "0",
                "::-webkit-calendar-picker-indicator": "calc(var(--space-1) * -1)",
            },
            "marginBottom": "0",
            "marginLeft": {
                "default": "0",
                "::-webkit-calendar-picker-indicator": {
                    "default": "var(--space-1)",
                    "[type='time']": "0",
                },
            },
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
                "::selection": "var(--text-field-selection-color)",
            },
            "backgroundImage": "none",
            "boxSizing": {
                "default": "border-box",
                "::-webkit-calendar-picker-indicator": "content-box",
            },
            "color": {
                "default": "inherit",
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                "::placeholder": "var(--accent-12)",
            },
            "fontFamily": "inherit",
            "fontSize": "inherit",
            "fontWeight": "normal",
            "fontStyle": "normal",
            "lineHeight": "inherit",
            "letterSpacing": "inherit",
            "textTransform": "inherit",
            "wordSpacing": "inherit",
            "outlineStyle": "none",
            "outlineWidth": "medium",
            "outlineColor": "currentcolor",
            "outlineOffset": "0",
            "whiteSpace": "pre-wrap",
            "WebkitTapHighlightColor": "transparent",
            "cursor": {
                "default": "text",
                ":is(:disabled, :read-only):placeholder-shown": "var(--cursor-disabled)",
            },
            "WebkitTextFillColor": {
                ":is(:disabled, :read-only)": "var(--gray-a11)",
                ":autofill": "var(--gray-12)",
            },
            "width": {
                "default": "100%",
                "::-webkit-calendar-picker-indicator": "var(--text-field-native-icon-size)",
            },
            "display": "flex",
            "alignItems": "center",
            "textAlign": "inherit",
            "borderRadius": {
                "::-webkit-calendar-picker-indicator": "calc(var(--text-field-border-radius) - 2px)"
            },
            "borderTopLeftRadius": "var(--rx-text-field-radius-left)",
            "borderBottomLeftRadius": "var(--rx-text-field-radius-left)",
            "borderTopRightRadius": "var(--rx-text-field-radius-right)",
            "borderBottomRightRadius": "var(--rx-text-field-radius-right)",
            "textIndent": {
                "default": "var(--rx-text-field-indent)",
                ":is([type='date'], [type='datetime-local'], [type='time'], [type='week'], [type='month'])": "0",
            },
            "paddingTop": {
                "default": "0",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "paddingLeft": {
                "default": "0",
                ":is([type='date'], [type='datetime-local'], [type='time'], [type='week'], [type='month'])": "var(--rx-text-field-padding-left)",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "paddingRight": {
                "default": "0",
                ":is([type='date'], [type='datetime-local'], [type='time'], [type='week'], [type='month'])": "var(--rx-text-field-padding-right)",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "height": {
                "::-webkit-calendar-picker-indicator": "var(--text-field-native-icon-size)"
            },
            "paddingBottom": {
                "default": "0px",
                "::-webkit-calendar-picker-indicator": "var(--space-1)",
            },
            "backgroundClip": {":autofill": "text"},
            "userSelect": {"::placeholder": "none"},
            "opacity": {
                "::placeholder": {"default": 0.6, ":is(:disabled, :read-only)": 0.5}
            },
        },
        {
            "boxSizing": "border-box",
            "flexShrink": 0,
            "display": "flex",
            "alignItems": "center",
            "cursor": "var(--rx-text-field-slot-cursor, text)",
            "gap": "var(--rx-text-field-slot-gap)",
            "paddingLeft": "var(--rx-text-field-slot-padding)",
            "paddingRight": "var(--rx-text-field-slot-padding)",
            "color": "var(--rx-text-field-slot-color)",
            "order": -1,
            "marginLeft": "calc(var(--text-field-border-width) * -1)",
            "marginRight": "0",
        },
        {
            "boxSizing": "border-box",
            "flexShrink": 0,
            "display": "flex",
            "alignItems": "center",
            "cursor": "var(--rx-text-field-slot-cursor, text)",
            "gap": "var(--rx-text-field-slot-gap)",
            "paddingLeft": "var(--rx-text-field-slot-padding)",
            "paddingRight": "var(--rx-text-field-slot-padding)",
            "color": "var(--rx-text-field-slot-color)",
            "order": 0,
            "marginLeft": "0",
            "marginRight": "calc(var(--text-field-border-width) * -1)",
        },
        {
            "boxSizing": "border-box",
            "flexShrink": 0,
            "display": "flex",
            "alignItems": "center",
            "cursor": "var(--rx-text-field-slot-cursor, text)",
            "gap": "var(--rx-text-field-slot-gap)",
            "paddingLeft": "var(--rx-text-field-slot-padding)",
            "paddingRight": "var(--rx-text-field-slot-padding)",
            "color": "var(--accent-a11)",
            "order": -1,
            "marginLeft": "calc(var(--text-field-border-width) * -1)",
            "marginRight": "0",
        },
    ]


def test_text_field_bound_to_state(
    ui_plugin: UIPlugin,
):
    """An input a state controls is wrapped to keep what is typed, with the class names of its styles."""
    component = rx.ui.text_field(
        value=FieldState.text,
        on_change=FieldState.set_text,
        id="bound",
        size=rx.breakpoints(initial="1", md="3"),  # pyright: ignore[reportArgumentType]
        variant="classic",
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_14080a3bf5_c"],
        "children": [
            {
                "name": "DebounceInput",
                "props": [
                    "className:sx_7ad96f65e5_c",
                    '"data-rx-text-field-input":""',
                    "debounceTimeout:300",
                    'element:"input"',
                    'id:"bound"',
                    "inputRef:ref_bound",
                    'onChange:((_e) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_text_field____field_state.set_text", ({ ["text"] : _e?.["target"]?.["value"] }), ({  })))], [_e], ({  }))))',
                    "spellCheck:false",
                    'value:(isNotNullOrUndefined(reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.text_rx_state_) ? reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.text_rx_state_ : "")',
                ],
                "children": [],
            }
        ],
    }


def test_text_field_optional_value(
    ui_plugin: UIPlugin,
):
    """A value that may be None is an empty string to React, and an autocomplete bound to a bool is on or off."""
    component = rx.ui.input(
        value=FieldState.maybe,
        auto_complete=FieldState.complete,  # pyright: ignore[reportArgumentType]
        read_only=True,
    )
    assert component.render() == {
        "name": '"div"',
        "props": ["className:sx_ff3fb9d45c_c"],
        "children": [
            {
                "name": '"input"',
                "props": [
                    'autoComplete:(reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.complete_rx_state_ ? "on" : "off")',
                    "className:sx_345c25de08_c",
                    '"data-rx-text-field-input":""',
                    "readOnly:true",
                    "spellCheck:false",
                    'value:(isNotNullOrUndefined((pyAnd(!((reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.maybe_rx_state_?.valueOf?.() === null?.valueOf?.())), () => (!((reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.maybe_rx_state_?.valueOf?.() === undefined?.valueOf?.())))) ? reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.maybe_rx_state_ : "")) ? (pyAnd(!((reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.maybe_rx_state_?.valueOf?.() === null?.valueOf?.())), () => (!((reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.maybe_rx_state_?.valueOf?.() === undefined?.valueOf?.())))) ? reflex___state____state__tests___units___reflex_components_ui___components___test_text_field____field_state.maybe_rx_state_ : "") : "")',
                ],
                "children": [],
            }
        ],
    }


def test_text_field_unknown_variant(ui_plugin: UIPlugin):
    """A variant a text field does not have is an error that lists the ones it has."""
    with pytest.raises(StyleError) as error:
        rx.ui.input(variant="solid")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == 'rx.ui.text_field_root: unknown variant "solid". The values are "classic", "surface", "soft".'
    )


def test_text_field_unknown_slot_side(ui_plugin: UIPlugin):
    """So is the side of a slot."""
    with pytest.raises(TypeError) as error:
        rx.ui.input.slot("a", side="top")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == "Invalid var passed for prop TextFieldSlot.side, expected type typing.Literal['left', 'right'], got value 'top' of type <class 'str'>."
    )


def test_text_field_script_is_only_for_slots(ui_plugin: UIPlugin):
    """The one script of a text field gives its input the focus from a slot."""
    script = "$/reflex-ui/behaviors/text-field.js"
    assert script not in rx.ui.input(placeholder="a")._get_all_imports()
    assert rx.ui.input(rx.ui.input.slot("a"))._get_all_imports()[script] == [
        ImportVar(tag="focusField")
    ]
    assert "react-debounce-input@3.3.0" not in rx.ui.input()._get_all_imports()
