"""Tests for implicit computed-var dependencies (dep_tracking registry)."""

import pytest
import reflex_i18n
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


def test_format_computed_var_gains_locale_dependency():
    from reflex_i18n import format_number
    from reflex_i18n.state import I18nState

    import reflex as rx

    register_implicit_dependency((format_number,), lambda: I18nState.locale)
    i18n_name = I18nState.get_full_name()

    class PriceState(rx.State):
        amount: float = 0.0

        @rx.var
        def label(self) -> str:
            return format_number(self.amount)

    deps = PriceState.computed_vars["label"]._deps(objclass=PriceState)
    assert deps.get(i18n_name) == {"locale"}
    assert "amount" in deps[PriceState.get_full_name()]


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


def test_inline_imported_helper_gains_locale_dependency():
    from reflex_i18n import gettext
    from reflex_i18n.state import I18nState

    import reflex as rx

    register_implicit_dependency((gettext,), lambda: I18nState.locale)

    class InlineImportState(rx.State):
        @rx.var
        def greeting(self) -> str:
            from reflex_i18n import gettext as _

            return _("Hello")

    deps = InlineImportState.computed_vars["greeting"]._deps(objclass=InlineImportState)
    assert deps.get(I18nState.get_full_name()) == {"locale"}


def test_combined_load_helper_gains_locale_dependency():
    # Python 3.13+ fuses consecutive LOAD_FASTs; a helper passed as a value
    # next to `self` (or any local) arrives in a combined opcode.
    from reflex_i18n import gettext
    from reflex_i18n.state import I18nState

    import reflex as rx

    register_implicit_dependency((gettext,), lambda: I18nState.locale)

    class CombinedLoadState(rx.State):
        tags: list[str] = []

        @rx.var
        def translated_tags(self) -> str:
            from reflex_i18n import gettext as _

            return ", ".join(map(_, self.tags))

        @rx.var
        def translated_first(self) -> str:
            from reflex_i18n import gettext as _

            items = self.tags
            return next(map(_, items), "")

    i18n_name = I18nState.get_full_name()
    own_name = CombinedLoadState.get_full_name()

    deps = CombinedLoadState.computed_vars["translated_tags"]._deps(
        objclass=CombinedLoadState
    )
    assert deps.get(i18n_name) == {"locale"}
    assert "tags" in deps[own_name]

    # The helper fused with an untracked plain local (not `self`).
    first_deps = CombinedLoadState.computed_vars["translated_first"]._deps(
        objclass=CombinedLoadState
    )
    assert first_deps.get(i18n_name) == {"locale"}


def test_module_qualified_helper_gains_locale_dependency():
    from reflex_i18n.state import I18nState

    import reflex as rx

    register_implicit_dependency((reflex_i18n.format_number,), lambda: I18nState.locale)

    class QualifiedState(rx.State):
        amount: float = 0.0

        @rx.var
        def via_global_module(self) -> str:
            # `reflex_i18n` is a module global of this test module.
            return reflex_i18n.format_number(self.amount)

        @rx.var
        def via_closure_module_chain(self) -> str:
            # `rx` is closure-captured; `.i18n` is a submodule attribute.
            return rx.i18n.format_number(self.amount)

        @rx.var
        def via_inline_import(self) -> str:
            import reflex_i18n as i18n

            return i18n.format_number(self.amount)

    i18n_name = I18nState.get_full_name()
    for name in ("via_global_module", "via_closure_module_chain", "via_inline_import"):
        deps = QualifiedState.computed_vars[name]._deps(objclass=QualifiedState)
        assert deps.get(i18n_name) == {"locale"}, name
        assert "amount" in deps[QualifiedState.get_full_name()], name


def test_nested_function_helper_gains_locale_dependency():
    from reflex_i18n import gettext as _
    from reflex_i18n.state import I18nState

    import reflex as rx

    register_implicit_dependency((_,), lambda: I18nState.locale)

    class NestedState(rx.State):
        tags: list[str] = []

        @rx.var
        def via_lambda_closure(self) -> str:
            # `_` reaches the lambda through the getter's closure.
            return ", ".join(map(lambda tag: _(tag), self.tags))  # noqa: C417

        @rx.var
        def via_lambda_global(self) -> str:
            # The lambda's own globals are the enclosing function's.
            return ", ".join(map(lambda tag: reflex_i18n.gettext(tag), self.tags))  # noqa: C417

    i18n_name = I18nState.get_full_name()
    for name in ("via_lambda_closure", "via_lambda_global"):
        deps = NestedState.computed_vars[name]._deps(objclass=NestedState)
        assert deps.get(i18n_name) == {"locale"}, name
        assert "tags" in deps[NestedState.get_full_name()], name
