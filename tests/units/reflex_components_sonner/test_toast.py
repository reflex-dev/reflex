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


@pytest.mark.parametrize(
    ("toast_id", "expected"),
    [
        (
            "toast's-id",
            '''(() => refs['__toast'].dismiss("toast's-id"))''',
        ),
        (
            'toast"-id',
            r'''(() => refs['__toast'].dismiss("toast\"-id"))''',
        ),
        (
            "toast\nid",
            r'''(() => refs['__toast'].dismiss("toast\nid"))''',
        ),
        (
            "<reflex.Var>x</reflex.Var>",
            r'''(() => refs['__toast'].dismiss("\u003creflex.Var>x\u003c/reflex.Var>"))''',
        ),
    ],
)
def test_toast_dismiss_serializes_string_id(toast_id: str, expected: str):
    """Serialize string IDs as opaque JavaScript string literals."""
    event = Toaster.toast_dismiss(toast_id)
    function = next(value for key, value in event.args if str(key) == "function")

    assert str(function) == expected
