"""Tests for implicit computed-var dependencies (dep_tracking registry)."""

import pytest
from reflex_base.vars.dep_tracking import (
    _implicit_dependency_providers,
    register_implicit_dependency,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate the implicit-dependency registry and framework dep edges.

    Defining a state whose computed var depends on ``I18nState.locale``
    registers a permanent cross-state edge on the shared ``I18nState`` class.
    Snapshot and restore those edges so throwaway test states do not pollute
    later tests.

    Yields:
        None
    """
    from reflex_i18n.state import I18nState

    saved = dict(_implicit_dependency_providers)
    _implicit_dependency_providers.clear()
    saved_deps = {k: set(v) for k, v in I18nState._var_dependencies.items()}
    saved_dirty = set(I18nState._potentially_dirty_states)
    yield
    _implicit_dependency_providers.clear()
    _implicit_dependency_providers.update(saved)
    I18nState._var_dependencies = saved_deps
    I18nState._potentially_dirty_states = saved_dirty


def test_gettext_computed_var_gains_locale_dependency():
    from reflex_i18n import gettext as _
    from reflex_i18n.state import I18nState

    import reflex as rx

    register_implicit_dependency((_,), lambda: I18nState.locale)
    i18n_name = I18nState.get_full_name()

    class TranslatedState(rx.State):
        name: str = ""

        @rx.var
        def greeting(self) -> str:
            return _("Hello")

        @rx.var
        def greeting_named(self) -> str:
            return _("Hi ") + self.name

    greeting_deps = TranslatedState.computed_vars["greeting"]._deps(
        objclass=TranslatedState
    )
    assert greeting_deps.get(i18n_name) == {"locale"}

    named_deps = TranslatedState.computed_vars["greeting_named"]._deps(
        objclass=TranslatedState
    )
    assert named_deps.get(i18n_name) == {"locale"}
    assert "name" in named_deps[TranslatedState.get_full_name()]


def test_no_registration_no_extra_dependency():
    import reflex as rx

    class PlainState(rx.State):
        n: int = 0

        @rx.var
        def doubled(self) -> int:
            return self.n * 2

    deps = PlainState.computed_vars["doubled"]._deps(objclass=PlainState)
    assert deps == {PlainState.get_full_name(): {"n"}}


def test_provider_returning_none_adds_nothing():
    import reflex as rx

    def marker() -> str:
        return "x"

    register_implicit_dependency((marker,), lambda: None)

    class UsesMarker(rx.State):
        @rx.var
        def value(self) -> str:
            return marker()

    deps = UsesMarker.computed_vars["value"]._deps(objclass=UsesMarker)
    assert deps == {}


def test_helper_method_recursion_detects_dependency():
    from reflex_i18n import gettext as _
    from reflex_i18n.state import I18nState

    import reflex as rx

    register_implicit_dependency((_,), lambda: I18nState.locale)
    i18n_name = I18nState.get_full_name()

    class HelperState(rx.State):
        @rx.var
        def label(self) -> str:
            return self._translated()

        def _translated(self) -> str:
            return _("Save")

    deps = HelperState.computed_vars["label"]._deps(objclass=HelperState)
    assert deps.get(i18n_name) == {"locale"}
