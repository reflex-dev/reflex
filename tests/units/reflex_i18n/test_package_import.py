"""Tests for the package's import-time side effects.

State registration is a process-global, irreversible side effect, so these run
in a fresh interpreter via a subprocess rather than the shared test process
(where importing ``reflex_i18n.state`` elsewhere would already have registered
``I18nState``).
"""

import subprocess
import sys
import textwrap


def _run_snippet(body: str) -> None:
    """Run a Python snippet in a clean interpreter, asserting it exits 0.

    Args:
        body: The snippet source (dedented before running).
    """
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(body)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_importing_package_does_not_register_state():
    """Importing the package must not register I18nState until an app opts in."""
    # Regression: the reflex CLI imports every reflex.cli entry point at
    # startup, which imports reflex_i18n; that must not attach I18nState (and
    # its locale cookie) to apps that never use i18n.
    _run_snippet("""
        import reflex_i18n.cli  # the reflex.cli entry point target
        import reflex_i18n
        from reflex.state import all_base_state_classes

        def i18n_registered() -> bool:
            return any("i18n" in name.lower() for name in all_base_state_classes)

        assert not i18n_registered(), sorted(all_base_state_classes)

        # Opting in (as an app's rxconfig does) registers the state.
        reflex_i18n.I18nPlugin(locales=["en"])
        assert i18n_registered(), sorted(all_base_state_classes)
    """)


def test_state_attributes_accessible_and_register_on_access():
    """Accessing I18nState/set_locale resolves them and registers state."""
    _run_snippet("""
        import reflex_i18n
        from reflex.state import all_base_state_classes

        assert not any("i18n" in n.lower() for n in all_base_state_classes)

        assert reflex_i18n.I18nState.get_full_name()
        assert callable(reflex_i18n.set_locale)
        assert any("i18n" in n.lower() for n in all_base_state_classes)

        try:
            reflex_i18n.does_not_exist
        except AttributeError:
            pass
        else:
            raise AssertionError("expected AttributeError for unknown attribute")
    """)


def test_gettext_computed_var_gets_locale_edge_without_plugin_or_state_import():
    """Importing gettext alone must wire the retranslation dependency."""
    # Regression: the implicit-dep provider lives in .runtime (next to gettext),
    # not .state, so a computed var scanned before I18nPlugin is constructed (as
    # in a backend worker) still gains its edge to I18nState.locale.
    _run_snippet("""
        # Mirror a backend worker importing the app module: no I18nPlugin
        # construction, no explicit reflex_i18n.state import.
        import reflex as rx
        from reflex_i18n import gettext as _

        class GreetState(rx.State):
            @rx.var
            def greeting(self) -> str:
                return _("Hello")

        from reflex_i18n.state import I18nState
        deps = GreetState.computed_vars["greeting"]._deps(objclass=GreetState)
        assert deps.get(I18nState.get_full_name()) == {"locale"}, deps
    """)
