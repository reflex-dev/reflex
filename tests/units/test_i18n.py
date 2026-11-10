"""Tests for the reflex.i18n public API module."""

import subprocess
import sys

import reflex as rx


def test_reflex_i18n_defers_state_registration():
    # Importing reflex.i18n must not import reflex_i18n.state (which registers
    # I18nState as a global substate); accessing the deferred names does.
    # Subprocess: the check needs a fresh interpreter with no i18n modules
    # imported yet.
    code = (
        "import sys\n"
        "import reflex.i18n\n"
        "assert 'reflex_i18n.state' not in sys.modules, 'state imported eagerly'\n"
        "assert reflex.i18n.I18nState is not None\n"
        "assert 'reflex_i18n.state' in sys.modules\n"
        "assert callable(reflex.i18n.set_locale)\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_i18n_names_leave_star_import_without_reflex_i18n():
    # reflex-i18n is optional: without it, `from reflex import *` must not
    # resolve its names, while explicit access still reports the missing package.
    code = (
        "import sys\n"
        "sys.modules['reflex_i18n'] = None\n"
        "import reflex as rx\n"
        "names = {'i18n', 't', 'gettext', 'I18nPlugin', 'set_locale'}\n"
        "assert names.isdisjoint(rx.__all__), names & set(rx.__all__)\n"
        "try:\n"
        "    rx.t\n"
        "except ImportError as e:\n"
        "    assert 'reflex-i18n' in str(e), e\n"
        "else:\n"
        "    raise AssertionError('rx.t resolved without reflex-i18n')\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_i18n_names_exported_with_reflex_i18n():
    # The generated stub re-exports rx.t and rx.i18n through __all__.
    assert {"i18n", "t", "gettext", "I18nPlugin", "set_locale"} <= set(rx.__all__)
