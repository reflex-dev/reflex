"""Tests for the intro form block."""

from reflex_components_internal.blocks.intro_form import intro_form

import reflex as rx


def test_intro_form_appends_a_tuple_of_submit_events() -> None:
    """A tuple of extra submit events is appended like a list of them."""
    form = intro_form(on_submit=(rx.console_log("first"), rx.console_log("second")))
    # the form's submit handler is a hook that dispatches its events
    hooks = "".join(str(hook) for hook in form._get_all_hooks())

    assert '"first"' in hooks
    assert '"second"' in hooks
