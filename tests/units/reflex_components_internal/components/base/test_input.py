"""Accessibility checks for input controls."""

from reflex_components_internal.components.base.input import HighLevelInput


def test_clear_button_has_an_accessible_name():
    """The icon-only clear button announces its purpose."""
    assert '"aria-label":"Clear input"' in str(HighLevelInput.create(id="email"))
