"""Tests for shared font-family configuration."""

from reflex_site_shared import styles
from reflex_site_shared.styles import fonts


def test_shared_styles_use_configurable_font_variables():
    """Shared Python styles should honor consumer font-family overrides."""
    assert styles.SANS == "var(--font-instrument-sans)"
    assert styles.BASE_STYLE["font_family"] == "var(--font-instrument-sans)"
    assert fonts.font_family == "var(--font-instrument-sans)"
    assert fonts.code["font-family"] == "var(--font-jetbrains)"


def test_styles_module_does_not_expose_unusable_stylesheet_paths():
    """Stylesheet injection should remain the compiler plugin's responsibility."""
    assert not hasattr(styles, "STYLESHEETS")
