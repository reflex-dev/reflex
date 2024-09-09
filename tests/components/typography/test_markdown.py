import pytest

import reflex as rx
from reflex.components.markdown import Markdown


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("h1", "Heading"),
        ("h2", "Heading"),
        ("h3", "Heading"),
        ("h4", "Heading"),
        ("h5", "Heading"),
        ("h6", "Heading"),
        ("p", "Text"),
        ("ul", "ul"),
        ("ol", "ol"),
        ("li", "li"),
        ("a", "Link"),
        ("code", "Code"),
    ],
)
def test_get_component(tag, expected):
    """Test getting a component from the component map.

    Args:
        tag: The tag to get.
        expected: The expected component.
    """
    md = Markdown.create("# Hello")
    assert tag in md.component_map  # type: ignore
    assert md.get_component(tag).tag == expected  # type: ignore


def test_set_component_map():
    """Test setting the component map."""
    component_map = {
        "h1": lambda value: rx.box(rx.heading(value, as_="h1"), padding="1em"),
        "p": lambda value: rx.box(rx.text(value), padding="1em"),
    }
    md = Markdown.create("# Hello", component_map=component_map)

    # Check that the new tags have been added.
    assert md.get_component("h1").tag == "Box"  # type: ignore
    assert md.get_component("p").tag == "Box"  # type: ignore

    # Make sure the old tags are still there.
    assert md.get_component("h2").tag == "Heading"  # type: ignore
