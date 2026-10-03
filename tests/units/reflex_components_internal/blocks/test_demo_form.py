"""Tests for the demo form block."""

import re

import pytest
from reflex_components_internal.blocks.demo_form import demo_form, demo_form_dialog

import reflex as rx

RENDER_PROP_PATTERN = re.compile(r"render:\(jsx\((\w+)")
TRIGGER_LABEL = "Show me the demo form"


def test_demo_form_dialog_omits_trigger_when_not_given() -> None:
    """A dialog without a trigger renders no trigger instead of an empty fragment."""
    rendered = str(demo_form_dialog())

    assert "Dialog.Trigger" not in rendered
    # A Fragment cannot receive the props and ref that a base-ui render prop
    # forwards to it, which makes React complain at runtime.
    assert "Fragment" not in RENDER_PROP_PATTERN.findall(rendered)


def test_demo_form_dialog_renders_given_trigger() -> None:
    """A dialog with a trigger renders it through the trigger's render prop."""
    # The dialog body has fixed copy of its own, so the label must be one that
    # only the trigger can contribute.
    assert TRIGGER_LABEL not in str(demo_form_dialog())

    rendered = str(demo_form_dialog(trigger=rx.el.button(TRIGGER_LABEL)))

    assert "Dialog.Trigger" in rendered
    assert TRIGGER_LABEL in rendered


def test_demo_form_appends_a_tuple_of_submit_events() -> None:
    """A tuple of extra submit events is appended like a list of them."""
    form = demo_form(on_submit=(rx.console_log("first"), rx.console_log("second")))
    # the form's submit handler is a hook that dispatches its events
    hooks = "".join(str(hook) for hook in form._get_all_hooks())

    assert '"first"' in hooks
    assert '"second"' in hooks


def test_demo_form_rejects_a_string_as_submit_events() -> None:
    """A string is a sequence, but not one of events."""
    with pytest.raises(TypeError, match="not the string"):
        demo_form(on_submit="first")  # pyright: ignore[reportArgumentType]
