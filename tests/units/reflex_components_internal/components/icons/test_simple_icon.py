"""Tests for immutable SimpleIcon construction."""

import pytest
from reflex_components_internal.components.icons.simple_icon import SimpleIcon


@pytest.mark.parametrize("icon_name", ["SiGithub", "SiPython"])
def test_simple_icon_renders_and_imports_requested_icon(icon_name: str):
    """The requested icon renders with its props and matching library import.

    Args:
        icon_name: The icon component to create.
    """
    icon = SimpleIcon.create(icon_name, color="red", size=24)
    rendered = icon.render()

    assert rendered["name"] == icon_name
    assert 'color:"red"' in rendered["props"]
    assert "size:24" in rendered["props"]
    assert icon.add_imports()[icon.library].tag == icon_name
    assert SimpleIcon.tag == "SiReact"
