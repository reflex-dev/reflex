"""Sonner toast component tests."""

import json

import pytest
from pytest_mock import MockerFixture
from reflex_base.style import Style
from reflex_base.utils.exceptions import InvalidPropValueError
from reflex_components_sonner.toast import Toaster, ToastProps


def test_toaster_hotkey_accepts_key_list():
    """Sonner reads `hotkey` as an array of KeyboardEvent keys and codes."""
    toaster = Toaster.create(hotkey=["altKey", "KeyT"])
    assert 'hotkey:["altKey", "KeyT"]' in str(toaster)


def test_toast_button_styles_use_sonner_prop_names(mocker: MockerFixture):
    """The button style props serialize to Sonner's option names as they are."""
    deprecate = mocker.patch("reflex_base.utils.console.deprecate")
    props = ToastProps(
        action_button_style=Style({"background_color": "red"}),
        cancel_button_style=Style({"color": "white"}),
    )  # pyright: ignore[reportCallIssue]

    deprecate.assert_not_called()
    assert json.loads(props.json()) == {
        "actionButtonStyle": {"backgroundColor": "red"},
        "cancelButtonStyle": {"color": "white"},
    }


def test_toast_deprecated_button_styles(mocker: MockerFixture):
    """The plural names still work, warn, and serialize like the singular ones."""
    deprecate = mocker.patch("reflex_base.utils.console.deprecate")
    action_style = Style({"background_color": "red"})
    cancel_style = Style({"color": "white"})
    props = ToastProps(
        action_button_styles=action_style,
        cancel_button_styles=cancel_style,
    )  # pyright: ignore[reportCallIssue]

    assert deprecate.call_args_list == [
        mocker.call(
            feature_name="The `action_button_styles` toast prop",
            reason="Use `action_button_style` instead, which matches Sonner's option name",
            deprecation_version="0.11.1",
            removal_version="1.0",
        ),
        mocker.call(
            feature_name="The `cancel_button_styles` toast prop",
            reason="Use `cancel_button_style` instead, which matches Sonner's option name",
            deprecation_version="0.11.1",
            removal_version="1.0",
        ),
    ]
    assert props.action_button_style is action_style
    assert props.cancel_button_style is cancel_style
    assert props.action_button_styles is None
    assert props.cancel_button_styles is None
    assert json.loads(props.json()) == {
        "actionButtonStyle": {"backgroundColor": "red"},
        "cancelButtonStyle": {"color": "white"},
    }


def test_toast_button_style_and_deprecated_name_together():
    """Passing a button style under both names is ambiguous, so it raises."""
    with pytest.raises(InvalidPropValueError) as action_error:
        Toaster.send_toast(
            "Saved",
            action_button_style=Style({"color": "red"}),
            action_button_styles=Style({"color": "blue"}),
        )
    with pytest.raises(InvalidPropValueError) as cancel_error:
        Toaster.send_toast(
            "Saved",
            cancel_button_style=Style({"color": "red"}),
            cancel_button_styles=Style({"color": "blue"}),
        )

    assert str(action_error.value) == (
        "Pass only one of 'action_button_style' and the deprecated "
        "'action_button_styles' to 'rx.toast'."
    )
    assert str(cancel_error.value) == (
        "Pass only one of 'cancel_button_style' and the deprecated "
        "'cancel_button_styles' to 'rx.toast'."
    )


def test_toaster_toast_options_button_styles():
    """Default toast options passed to the provider carry Sonner's option names."""
    toaster = Toaster.create(
        toast_options=ToastProps(
            action_button_style=Style({"background_color": "red"}),
            cancel_button_style=Style({"color": "white"}),
        )  # pyright: ignore[reportCallIssue]
    )

    assert str(toaster.toast_options) == (  # pyright: ignore[reportAttributeAccessIssue]
        '({ ["actionButtonStyle"] : ({ ["backgroundColor"] : "red" }), '
        '["cancelButtonStyle"] : ({ ["color"] : "white" }) })'
    )
