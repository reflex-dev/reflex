"""Tests for the demo form block."""

import re

from reflex_base.vars.sequence import LiteralStringVar
from reflex_components_internal.blocks.demo_form import demo_form, demo_form_dialog
from reflex_components_internal.blocks.telemetry.posthog import (
    PHONE_NUMBER_KEY,
    track_demo_form_posthog_submission,
)

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


def test_demo_form_asks_for_an_optional_phone_number() -> None:
    """The phone number is a tel input that the form can be submitted without."""
    rendered = str(demo_form())
    field = re.search(rf'name:"{PHONE_NUMBER_KEY}"[^}}]*', rendered)

    assert field is not None
    assert 'type:"tel"' in field.group()
    assert "required:false" in field.group()


def test_demo_request_tracking_includes_the_phone_number() -> None:
    """PostHog receives the phone number with the rest of the demo request."""
    event = track_demo_form_posthog_submission({PHONE_NUMBER_KEY: "+15551234567"})
    script = {str(name): value for name, value in event.args}["javascript_code"]
    assert isinstance(script, LiteralStringVar)
    script = script._var_value

    assert "posthog.capture('demo_request', props)" in script
    assert f'"{PHONE_NUMBER_KEY}": "+15551234567"' in script
