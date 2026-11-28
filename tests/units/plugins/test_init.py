"""Tests for the plugin API reflex.plugins re-exports."""

import reflex_base.plugins

import reflex.plugins


def test_reexports_reflex_base_plugins() -> None:
    """reflex.plugins offers every name of reflex_base.plugins, and the Radix plugin."""
    assert sorted(reflex.plugins.__all__) == sorted([
        *reflex_base.plugins.__all__,
        "RadixThemesPlugin",
    ])
    for name in reflex_base.plugins.__all__:
        assert getattr(reflex.plugins, name) is getattr(reflex_base.plugins, name)
