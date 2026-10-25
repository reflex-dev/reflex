"""Tests for the reflex.i18n public API module."""

import subprocess
import sys


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
