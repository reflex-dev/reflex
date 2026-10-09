"""Tests for the intro form block."""

import pytest
from reflex_components_internal.blocks.intro_form import intro_form

import reflex as rx


def test_intro_form_appends_a_tuple_of_submit_events() -> None:
    """A tuple of extra submit events is appended like a list of them."""
    form = intro_form(on_submit=(rx.console_log("first"), rx.console_log("second")))
    # the form's submit handler is a hook that dispatches its events
    hooks = "".join(str(hook) for hook in form._get_all_hooks())

    assert '"first"' in hooks
    assert '"second"' in hooks


def test_intro_form_rejects_a_string_as_submit_events() -> None:
    """A string is a sequence, but not one of events."""
    with pytest.raises(TypeError, match="not the string"):
        intro_form(on_submit="first")  # pyright: ignore[reportArgumentType]
