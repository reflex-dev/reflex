"""Accessibility checks for input controls."""

from reflex_components_internal.components.base.input import HighLevelInput


def test_clear_button_has_an_accessible_name():
    """The icon-only clear button announces its purpose."""
    assert '"aria-label":"Clear input"' in str(HighLevelInput.create(id="email"))


def test_input_root_takes_event_triggers_in_call_order():
    """The forwarded triggers keep call order, so compiles do not vary by hash seed."""
    from reflex_components_internal.components.base.input import InputRoot

    field = HighLevelInput.create(
        name="seats",
        on_focus=lambda _: [],
        on_blur=lambda _: [],
        on_change=lambda _: [],
        on_key_down=lambda _: [],
    )
    root = next(child for child in field.children if isinstance(child, InputRoot))
    assert list(root.event_triggers) == [
        "on_focus",
        "on_blur",
        "on_change",
        "on_key_down",
    ]
