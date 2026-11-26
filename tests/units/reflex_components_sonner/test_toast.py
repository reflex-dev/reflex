"""Sonner toast component tests."""

import json

from reflex_base.style import Style
from reflex_base.utils.imports import ImportVar
from reflex_components_lucide.icon import LUCIDE_LIBRARY, Icon
from reflex_components_sonner import toast
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


def test_toast_accepts_component_icon() -> None:
    """A compiled toast carries the icon expression and its import."""
    function = toast.success("Saved", icon=Icon.create(tag="check")).args[0][1]
    var_data = function._get_all_var_data()

    assert str(function) == (
        """(() => (refs['__toast']?.["success"]("Saved", """
        """({ ["icon"] : (jsx(LucideCheck, ({}))) }))))"""
    )
    assert var_data is not None
    assert dict(var_data.imports)[LUCIDE_LIBRARY] == (
        ImportVar(
            tag="Check",
            alias="LucideCheck",
            is_default=True,
            package_path="/dist/esm/icons/check.mjs",
        ),
    )
