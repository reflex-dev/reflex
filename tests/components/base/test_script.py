"""Test that Script from next/script renders correctly."""

import pytest

from reflex.components.base.script import Script
from reflex.state import BaseState


def test_script_inline():
    """Test inline scripts are rendered as children."""
    component = Script.create("let x = 42")
    render_dict = component.render()
    assert render_dict["name"] == "Script"
    assert not render_dict["contents"]
    assert len(render_dict["children"]) == 1
    assert render_dict["children"][0]["contents"] == '{"let x = 42"}'


def test_script_src():
    """Test src prop is rendered without children."""
    component = Script.create(src="foo.js")
    render_dict = component.render()
    assert render_dict["name"] == "Script"
    assert not render_dict["contents"]
    assert not render_dict["children"]
    assert 'src={"foo.js"}' in render_dict["props"]


def test_script_neither():
    """Specifying neither children nor src is a ValueError."""
    with pytest.raises(ValueError):
        Script.create()


class EvState(BaseState):
    """State for testing event handlers."""

    def on_ready(self):
        """Empty event handler."""
        pass

    def on_load(self):
        """Empty event handler."""
        pass

    def on_error(self):
        """Empty event handler."""
        pass


def test_script_event_handler():
    """Test event handlers are rendered as expected."""
    component = Script.create(
        src="foo.js",
        on_ready=EvState.on_ready,
        on_load=EvState.on_load,
        on_error=EvState.on_error,
    )
    render_dict = component.render()
    assert (
        f'onReady={{((...args) => ((addEvents([(Event("{EvState.get_full_name()}.on_ready", ({{  }})))], args, ({{  }})))))}}'
        in render_dict["props"]
    )
    assert (
        f'onLoad={{((...args) => ((addEvents([(Event("{EvState.get_full_name()}.on_load", ({{  }})))], args, ({{  }})))))}}'
        in render_dict["props"]
    )
    assert (
        f'onError={{((...args) => ((addEvents([(Event("{EvState.get_full_name()}.on_error", ({{  }})))], args, ({{  }})))))}}'
        in render_dict["props"]
    )
