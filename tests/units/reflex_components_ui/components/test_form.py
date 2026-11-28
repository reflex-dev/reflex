"""Tests for reflex_components_ui.components.form."""

import itertools
from collections.abc import Callable
from typing import Any

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_components_ui.components import form as form_module
from reflex_components_ui.plugin import UIPlugin

import reflex as rx


class FormState(rx.State):
    """What a form is bound to."""

    taken: bool = False

    @rx.event
    def clear(self):
        """Forget what the server found."""
        self.taken = False

    @rx.event
    def submit(self, data: dict[str, Any]):
        """Take what the form submits.

        Args:
            data: The values of the form.
        """


def test_form_parts(
    ui_plugin: UIPlugin,
    declared_styles: Callable[[Any], list[dict[str, Any]]],
):
    """A field names its control and points its label at it; a message with a condition is hidden until it holds, and the form reads the validity of its controls."""
    component = rx.ui.form(
        rx.ui.form.field(
            rx.ui.form.label("Email"),
            rx.ui.form.control(rx.ui.input(type="email", required=True, id="email")),
            rx.ui.form.message("Needed", match="valueMissing"),
            rx.ui.form.message("Always"),
            rx.ui.form.message("Forced", match="typeMismatch", force_match=True),
            name="email",
        ),
        rx.ui.form.message("Outside", match="valueMissing", name="email"),
        rx.ui.form.submit("Send"),
        id="signup",
    )
    assert component.render() == {
        "name": '"form"',
        "props": [
            "className:sx_5073704993_c",
            'id:"signup"',
            "onBlurCapture:((event) => { left(event); })",
            "onChangeCapture:((event) => { changed(event); })",
            "onInvalid:((event) => { invalid(event); })",
            "onReset:((event) => { cleared(event); })",
            "onSubmit:handleSubmit_ff7a0ed8ca0437fd853c637504ba1398",
            "ref:ref_signup",
        ],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_7fb5ccb001_c", '"data-rx-form-field":""'],
                "children": [
                    {
                        "name": '"label"',
                        "props": ["className:sx_3f1c4be050_c", 'htmlFor:"email"'],
                        "children": [{"contents": '"Email"'}],
                    },
                    {
                        "name": '"div"',
                        "props": ["className:sx_ff3fb9d45c_c"],
                        "children": [
                            {
                                "name": '"input"',
                                "props": [
                                    "className:sx_345c25de08_c",
                                    '"data-rx-text-field-input":""',
                                    'id:"email"',
                                    'name:"email"',
                                    "ref:ref_email",
                                    "required:true",
                                    "spellCheck:false",
                                    'type:"email"',
                                ],
                                "children": [],
                            }
                        ],
                    },
                    {
                        "name": '"span"',
                        "props": [
                            "className:sx_71d77c9098_c",
                            '"data-match":"valueMissing"',
                            '"data-rx-form-message":""',
                            "hidden:true",
                        ],
                        "children": [{"contents": '"Needed"'}],
                    },
                    {
                        "name": '"span"',
                        "props": [
                            "className:sx_71d77c9098_c",
                            '"data-rx-form-message":""',
                        ],
                        "children": [{"contents": '"Always"'}],
                    },
                    {
                        "name": '"span"',
                        "props": [
                            "className:sx_71d77c9098_c",
                            '"data-force":""',
                            '"data-match":"typeMismatch"',
                            '"data-rx-form-message":""',
                        ],
                        "children": [{"contents": '"Forced"'}],
                    },
                ],
            },
            {
                "name": '"span"',
                "props": [
                    "className:sx_71d77c9098_c",
                    '"data-match":"valueMissing"',
                    '"data-name":"email"',
                    '"data-rx-form-message":""',
                    "hidden:true",
                ],
                "children": [{"contents": '"Outside"'}],
            },
            {
                "name": '"button"',
                "props": ['type:"submit"'],
                "children": [{"contents": '"Send"'}],
            },
        ],
    }
    assert declared_styles(component) == [
        {"width": "100%"},
        {"display": "grid", "marginBottom": "10px"},
        {"fontSize": "15px", "fontWeight": "500", "lineHeight": "35px"},
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
        {"fontSize": "13px", "opacity": "0.8", "color": "white"},
        {"fontSize": "13px", "opacity": "0.8", "color": "white"},
        {"fontSize": "13px", "opacity": "0.8", "color": "white"},
        {"fontSize": "13px", "opacity": "0.8", "color": "white"},
        {},
    ]


def test_form_server_errors(
    ui_plugin: UIPlugin,
):
    """A field the server finds invalid says so on itself and on its control, shows the messages it forces, and its errors are cleared on a submit and on a reset."""
    component = rx.ui.form.root(
        rx.ui.form.field(
            rx.ui.form.control(rx.el.input(name="mine", id="code")),
            rx.ui.form.message("Taken", match="valid", force_match=FormState.taken),
            name="code",
            server_invalid=FormState.taken,
        ),
        on_submit=FormState.submit,
        on_clear_server_errors=FormState.clear,
    )
    assert component.render() == {
        "name": '"form"',
        "props": [
            "className:sx_5073704993_c",
            "onBlurCapture:((event) => { left(event); })",
            "onChangeCapture:((event) => { changed(event); })",
            "onInvalid:((event) => { invalid(event); })",
            'onReset:((event) => { cleared(event); (((...args) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_form____form_state.clear", ({  }), ({  })))], args, ({  })))))(event); })',
            "onSubmit:handleSubmit_21b393bf90a9dc94271acff60be1dacc",
            'onSubmitCapture:((event) => { (((...args) => (addEvents([(ReflexEvent("reflex___state____state.tests___units___reflex_components_ui___components___test_form____form_state.clear", ({  }), ({  })))], args, ({  })))))(event); })',
        ],
        "children": [
            {
                "name": '"div"',
                "props": [
                    "className:sx_7fb5ccb001_c",
                    '"data-invalid":(reflex___state____state__tests___units___reflex_components_ui___components___test_form____form_state.taken_rx_state_ ? "" : undefined)',
                    '"data-rx-form-field":""',
                    '"data-server-invalid":(reflex___state____state__tests___units___reflex_components_ui___components___test_form____form_state.taken_rx_state_ ? "" : undefined)',
                    "ref:(reflex___state____state__tests___units___reflex_components_ui___components___test_form____form_state.taken_rx_state_ ? focusInvalid : undefined)",
                ],
                "children": [
                    {
                        "name": '"input"',
                        "props": [
                            '"aria-invalid":(reflex___state____state__tests___units___reflex_components_ui___components___test_form____form_state.taken_rx_state_ || undefined)',
                            'id:"code"',
                            'name:"mine"',
                            "ref:ref_code",
                        ],
                        "children": [],
                    },
                    {
                        "name": '"span"',
                        "props": [
                            "className:sx_71d77c9098_c",
                            '"data-force":(reflex___state____state__tests___units___reflex_components_ui___components___test_form____form_state.taken_rx_state_ ? "" : undefined)',
                            '"data-match":"valid"',
                            '"data-rx-form-message":""',
                            "hidden:!(reflex___state____state__tests___units___reflex_components_ui___components___test_form____form_state.taken_rx_state_)",
                        ],
                        "children": [{"contents": '"Taken"'}],
                    },
                ],
            }
        ],
    }


def test_form_without_messages(
    ui_plugin: UIPlugin,
):
    """A form without a message is the form element of Reflex, with no script of its own."""
    component = rx.ui.form(
        rx.ui.form.field(
            rx.ui.form.label("Notes"),
            rx.ui.form.control(rx.ui.text_area(id="notes")),
            name="notes",
        ),
        rx.ui.form.validity_state("x"),
        rx.ui.form.submit(rx.ui.button("Send"), as_child=True),
    )
    assert component.render() == {
        "name": '"form"',
        "props": [
            "className:sx_5073704993_c",
            "onSubmit:handleSubmit_778c17e137b39fd18ce6e668f384d9a1",
        ],
        "children": [
            {
                "name": '"div"',
                "props": ["className:sx_7fb5ccb001_c", '"data-rx-form-field":""'],
                "children": [
                    {
                        "name": '"label"',
                        "props": ["className:sx_3f1c4be050_c", 'htmlFor:"notes"'],
                        "children": [{"contents": '"Notes"'}],
                    },
                    {
                        "name": '"div"',
                        "props": ["className:sx_246a7bce17_c"],
                        "children": [
                            {
                                "name": '"textarea"',
                                "props": [
                                    "className:sx_8eecb42f44_c",
                                    '"data-rx-text-area-input":""',
                                    'id:"notes"',
                                    'name:"notes"',
                                    "ref:ref_notes",
                                ],
                                "children": [],
                            }
                        ],
                    },
                ],
            },
            {"name": '"span"', "props": [], "children": [{"contents": '"x"'}]},
            {
                "name": '"button"',
                "props": ["className:sx_f2580dfc68_c", 'type:"submit"'],
                "children": [{"contents": '"Send"'}],
            },
        ],
    }


def test_form_control_takes_one_child(ui_plugin: UIPlugin):
    """A control renders one native form control."""
    with pytest.raises(ValueError) as error:
        rx.ui.form.control(rx.el.input(), rx.el.input())
    assert (
        str(error.value)
        == "FormControl can only have at most one child, got 2 children"
    )


def test_form_control_child_is_a_native_control(ui_plugin: UIPlugin):
    """Another kind of child is an error that says what to do with it."""
    with pytest.raises(TypeError) as error:
        rx.ui.form.control(rx.ui.checkbox("Agree"))
    assert (
        str(error.value)
        == "The child of rx.ui.form.control must render a native form control: rx.ui.input, rx.ui.text_area, rx.debounce_input, rx.el.input, rx.el.select or rx.el.textarea, not Text. Give other controls such as rx.ui.checkbox or rx.ui.select a `name` and place them under rx.ui.form.root or rx.ui.form.field instead."
    )


def test_form_message_unknown_match(ui_plugin: UIPlugin):
    """A condition a message cannot have is an error."""
    with pytest.raises(TypeError) as error:
        rx.ui.form.message("x", match="wrong")  # pyright: ignore[reportArgumentType]
    assert (
        str(error.value)
        == "Invalid var passed for prop FormMessage.match, expected type typing.Literal['badInput', 'patternMismatch', 'rangeOverflow', 'rangeUnderflow', 'stepMismatch', 'tooLong', 'tooShort', 'typeMismatch', 'valid', 'valueMissing'], got value 'wrong' of type <class 'str'>."
    )


def test_form_field_gives_its_control_an_id(
    ui_plugin: UIPlugin, monkeypatch: pytest.MonkeyPatch
):
    """A control without an id is given one for the label of its field."""
    monkeypatch.setattr(form_module, "_ids", itertools.count(4))
    field = rx.ui.form.field(
        rx.ui.form.label("Age"), rx.ui.form.control(name="years"), name="age"
    )
    assert field.render()["children"] == [
        {
            "name": '"label"',
            "props": ["className:sx_3f1c4be050_c", 'htmlFor:"rx-form-field-4"'],
            "children": [{"contents": '"Age"'}],
        },
        {
            "name": '"input"',
            "props": ['id:"rx-form-field-4"', 'name:"years"'],
            "children": [],
        },
    ]


def test_form_script_is_only_for_messages(ui_plugin: UIPlugin):
    """The script of a form reads validity for its messages, and nothing else."""
    script = "$/reflex-ui/behaviors/form-validity.js"
    plain = rx.ui.form(rx.ui.form.field(rx.ui.form.control(), name="a"))
    assert script not in plain._get_all_imports()
    with_message = rx.ui.form(rx.ui.form.message("x", match="valueMissing"))
    assert with_message._get_all_imports()[script] == [
        ImportVar(tag="invalid"),
        ImportVar(tag="changed"),
        ImportVar(tag="left"),
        ImportVar(tag="cleared"),
    ]
    invalid = rx.ui.form.field(rx.ui.form.control(), server_invalid=True)
    assert invalid._get_all_imports()[script] == [ImportVar(tag="focusInvalid")]
