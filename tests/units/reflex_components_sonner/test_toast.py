"""Sonner toast component tests."""

import json

import pytest
from reflex_base.style import Style
from reflex_components_sonner.toast import Toaster, ToastProps


def test_toaster_hotkey_accepts_key_list():
    """Sonner reads `hotkey` as an array of KeyboardEvent keys and codes."""
    toaster = Toaster.create(hotkey=["altKey", "KeyT"])
    assert 'hotkey:["altKey", "KeyT"]' in str(toaster)


def test_toast_button_styles_use_sonner_prop_names():
    """Serialize toast button styles with Sonner's singular option names."""
    props = ToastProps(
        action_button_styles=Style({"background_color": "red"}),
        cancel_button_styles=Style({"color": "white"}),
    )  # pyright: ignore[reportCallIssue]

    serialized = json.loads(props.json())

    assert serialized["actionButtonStyle"]["backgroundColor"] == "red"
    assert serialized["cancelButtonStyle"]["color"] == "white"
    assert "actionButtonStyles" not in serialized
    assert "cancelButtonStyles" not in serialized


@pytest.mark.parametrize("toast_id", ["toast's-id", 'toast"-id', "toast\nid"])
def test_toast_dismiss_serializes_string_id(toast_id: str):
    """Serialize string IDs as valid JavaScript string literals."""
    event = Toaster.toast_dismiss(toast_id)
    function = next(value for key, value in event.args if str(key) == "function")

    assert f".dismiss({json.dumps(toast_id)})" in str(function)
