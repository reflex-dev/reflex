"""Tests for the sectioning HTML elements."""

from reflex_components_core.el.elements.sectioning import H1, H2, H3, H4, H5, H6


def test_heading_docstrings_name_their_own_level():
    """Each heading element's docstring, shown in the docs, names its own tag."""
    assert [heading.__doc__ for heading in (H1, H2, H3, H4, H5, H6)] == [
        f"Display the h{level} element." for level in range(1, 7)
    ]
