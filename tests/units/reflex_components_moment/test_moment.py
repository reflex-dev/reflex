"""Tests for per-component Moment locale configuration."""

import pytest
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var
from reflex_components_moment.moment import Moment, MomentProvider


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


def test_react_moment_2_props_are_forwarded():
    """Moment 2.x props are passed to React instead of becoming CSS."""
    moment = Moment.create(
        "2024-03-14",
        utc=True,
        calendar={"sameDay": "[Today]"},
        from_="2024-03-01",
        to="2024-03-31",
        ago=True,
        element="span",
        fallback="Unknown date",
        filters=Var(_js_expr="[uppercase]", _var_type=list),
        renderers=Var(_js_expr="[customRenderer]", _var_type=list),
    )

    props = moment.render()["props"]
    assert "utc:true" in props
    assert any(prop.startswith("calendar:") and '"sameDay"' in prop for prop in props)
    assert 'from:"2024-03-01"' in props
    assert 'to:"2024-03-31"' in props
    assert "ago:true" in props
    assert 'element:"span"' in props
    assert 'fallback:"Unknown date"' in props
    assert "filters:[uppercase]" in props
    assert "renderers:[customRenderer]" in props
    assert "css:" not in props


def test_removed_filter_prop_has_migration_error():
    """The removed singular filter prop points users to the 2.x replacement."""
    with pytest.raises(TypeError, match=r"filter.*removed.*filters"):
        Moment.create("2024-03-14", filter="uppercase")


def test_invalid_format_typo_has_actionable_error():
    """A reported typo is not silently emitted as a CSS style."""
    with pytest.raises(TypeError, match=r"form_at.*not a react-moment prop.*format"):
        Moment.create("2024-03-14", form_at="YYYY")


def test_settings_prop_has_configuration_error():
    """Shared settings point users to the supported provider API."""
    with pytest.raises(
        TypeError, match=r"settings.*not a react-moment 2.x prop.*rx.moment_provider"
    ):
        Moment.create("2024-03-14", settings={"format": "YYYY"})


def test_moment_provider_exports_named_component_and_shared_props():
    """Provider props are forwarded and use the named react-moment export."""
    import reflex as rx

    assert rx.moment_provider is not None
    provider = MomentProvider.create(
        Moment.create("2024-03-14"),
        pool=True,
        interval=30000,
        locale="fr",
        format="D MMM YYYY",
        timezone="America/Los_Angeles",
    )

    assert provider.render()["name"] == "MomentProvider"
    props = provider.render()["props"]
    assert "pool:true" in props
    assert "interval:30000" in props
    assert 'locale:"fr"' in props
    assert 'format:"D MMM YYYY"' in props
    assert 'timezone:"America/Los_Angeles"' in props
    assert provider.add_imports() == {
        "react-moment@2.0.2": ImportVar(tag="MomentProvider")
    }
