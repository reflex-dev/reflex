"""Tests for per-component Moment locale configuration."""

import pytest
from reflex_base.vars.base import Var
from reflex_components_moment.moment import Moment


@pytest.mark.parametrize("props", [{}, {"locale": None}, {"locale": "en"}])
def test_default_locale_is_explicit_english(props):
    """Omitted and English locales do not inherit another component's locale.

    Args:
        props: The omitted or explicitly English locale configuration.
    """
    moment = Moment.create("2024-03-14", **props)
    assert 'locale:"en"' in moment.render()["props"]
    assert "moment/locale/en" not in moment.add_imports().values()


def test_literal_locale_import_is_preserved():
    """A component that requests French still imports and renders that locale."""
    moment = Moment.create("2024-03-14", locale="fr")
    assert 'locale:"fr"' in moment.render()["props"]
    assert moment.add_imports()[""] == "moment/locale/fr"


def test_reactive_locale_imports_all_locales():
    """Reactive locale selection remains available independently of the default."""
    locale = Var(_js_expr="selectedLocale", _var_type=str)
    moment = Moment.create("2024-03-14", locale=locale)
    assert "locale:selectedLocale" in moment.render()["props"]
    assert moment.add_imports()[""] == "moment/min/locales"
