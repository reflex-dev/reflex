"""Sonner toast component tests."""

import json

from reflex_base.style import Style
from reflex_components_sonner.toast import Toaster, ToasterRequest, ToastProps, toast


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


def test_toast_call_asks_the_app_for_its_toaster():
    """Every toast event carries the marker wrap the compiler looks for."""
    for event in (
        toast("Hello"),
        toast.error("Failed", description="Try again"),
        toast.dismiss("some-id"),
        toast.dismiss(),
    ):
        requests = [
            (priority, type(wrapper), wrapper.render())
            for _, arg in event.args
            if (var_data := arg._get_all_var_data()) is not None
            for priority, wrapper in var_data.app_wraps
        ]
        assert requests == [(44, ToasterRequest, ToasterRequest.create().render())]

    # Left in place, the marker renders nothing of its own.
    assert str(ToasterRequest.create()) == "jsx(Fragment,{},)"
