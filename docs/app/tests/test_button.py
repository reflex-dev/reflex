"""Coverage for the docs site's button helpers."""

import pytest
import reflex as rx

from reflex_docs.components.button import button, button_with_icon


@pytest.mark.parametrize(
    ("create", "args"),
    [(button, ("Go",)), (button_with_icon, ("Go", "github"))],
    ids=["button", "button_with_icon"],
)
@pytest.mark.parametrize("positional", [False, True], ids=["keyword", "positional"])
def test_click_handler_is_the_event_trigger(create, args, positional):
    """The click handler reaches the button as its event trigger, not as a style.

    Args:
        create: The button helper.
        args: The helper's positional arguments before the variant.
        positional: Whether to pass the handler positionally after the variant.
    """
    handler = rx.console_log("clicked")
    component = (
        create(*args, "primary", handler)
        if positional
        else create(*args, on_click=handler)
    )
    assert component.event_triggers == rx.el.button(on_click=handler).event_triggers
    assert component.style == {}
