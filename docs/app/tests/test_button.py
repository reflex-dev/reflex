"""Coverage for the docs site's button helpers."""

import functools

import pytest
import reflex as rx

from reflex_docs.components.button import button, button_with_icon


@pytest.mark.parametrize(
    "create",
    [button, functools.partial(button_with_icon, icon="github")],
    ids=["button", "button_with_icon"],
)
def test_on_click_is_the_click_handler(create):
    """``on_click`` reaches the button as its event trigger, not as a style.

    Args:
        create: The button helper.
    """
    handler = rx.console_log("clicked")
    component = create("Go", on_click=handler)
    assert component.event_triggers == rx.el.button(on_click=handler).event_triggers
    assert component.style == {}
