"""Test that element script renders correctly."""

import pytest

from reflex.components.base.script import Script


def test_script_inline():
    """Test inline scripts are rendered as children."""
    component = Script.create("let x = 42")
    render_dict = component.render()["children"][0]
    assert render_dict["name"] == '"script"'
    assert len(render_dict["children"]) == 1
    assert render_dict["children"][0]["contents"] == '"let x = 42"'


def test_script_src():
    """Test src prop is rendered without children."""
    component = Script.create(src="foo.js")
    render_dict = component.render()["children"][0]
    assert render_dict["name"] == '"script"'
    assert not render_dict["children"]
    assert 'src:"foo.js"' in render_dict["props"]


def test_script_neither():
    """Specifying neither children nor src is a ValueError."""
    with pytest.raises(ValueError):
        Script.create()
