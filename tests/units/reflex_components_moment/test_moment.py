"""Tests for per-component Moment locale configuration."""

from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var
from reflex_components_moment.moment import Moment, MomentProvider


def test_default_locale_is_inherited_from_root_english_provider():
    """Omitted locales read the nearest provider; the app root provides English."""
    moment = Moment.create("2024-03-14")
    assert not any(prop.startswith("locale:") for prop in moment.render()["props"])
    assert "moment/locale/en" not in moment.add_imports().values()

    root = moment._get_all_app_wrap_components()[10, "MomentProvider"]
    assert isinstance(root, MomentProvider)
    assert root.render()["props"] == ['locale:"en"']
    assert root.add_imports() == {}


def test_moment_in_memo_requests_root_provider():
    """A Moment inside rx.memo still wraps the app in the English provider."""
    import reflex as rx

    @rx.memo
    def memo_moment() -> rx.Component:
        return rx.moment("2024-03-14")

    assert (10, "MomentProvider") in memo_moment()._get_all_app_wrap_components()


def test_explicit_english_locale_is_preserved():
    """An explicit English locale overrides a provider locale."""
    moment = Moment.create("2024-03-14", locale="en")
    assert 'locale:"en"' in moment.render()["props"]
    assert "moment/locale/en" not in moment.add_imports().values()


def test_explicit_child_locale_overrides_provider():
    """An explicit child locale remains a per-instance provider override."""
    provider = MomentProvider.create(
        Moment.create("2024-03-14", locale="en"), locale="fr"
    )

    assert 'locale:"en"' in provider.children[0].render()["props"]


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


def test_undeclared_props_stay_css():
    """Props that react-moment does not accept keep the generic CSS behavior."""
    moment = Moment.create("2024-03-14", filter="blur(2px)")
    assert 'css:({ ["filter"] : "blur(2px)" })' in moment.render()["props"]


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
        "": "moment/locale/fr",
        "moment-timezone@0.6.5": "",
    }
    assert (
        ImportVar(tag="MomentProvider")
        in provider._get_all_imports()["react-moment@2.0.2"]
    )


def test_moment_provider_reactive_locale_imports_all_locales():
    """A reactive provider locale includes the available locale modules."""
    locale = Var(_js_expr="selectedLocale", _var_type=str)
    provider = MomentProvider.create(Moment.create("2024-03-14"), locale=locale)

    assert provider.add_imports() == {"": "moment/min/locales"}
