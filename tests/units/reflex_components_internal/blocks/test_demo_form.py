"""Tests for the demo form block."""

import re

from reflex_components_internal.blocks.demo_form import demo_form_dialog

import reflex as rx

RENDER_PROP_PATTERN = re.compile(r"render:\(jsx\((\w+)")


def test_demo_form_dialog_omits_trigger_when_not_given() -> None:
    """A dialog without a trigger renders no trigger instead of an empty fragment."""
    rendered = str(demo_form_dialog())

    assert "Dialog.Trigger" not in rendered
    # A Fragment cannot receive the props and ref that a base-ui render prop
    # forwards to it, which makes React complain at runtime.
    assert "Fragment" not in RENDER_PROP_PATTERN.findall(rendered)


def test_demo_form_dialog_renders_given_trigger() -> None:
    """A dialog with a trigger renders it through the trigger's render prop."""
    rendered = str(demo_form_dialog(trigger=rx.el.button("Book a Demo")))

    assert "Dialog.Trigger" in rendered
    assert "Book a Demo" in rendered
