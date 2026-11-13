import json

from reflex_base.style import Style
from reflex_components_sonner.toast import ToastProps


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
