"""Tests for reflex_base.utils.imports module-level behavior."""

import subprocess
import sys

from reflex_base import constants
from reflex_base.utils.imports import LEGACY_FRONTEND_SPECIFIERS, merge_imports


def test_imports_module_is_importable_first():
    """The module must import cleanly as the first reflex import.

    Regression: it is imported by ``reflex_base.constants`` submodules, so it
    cannot itself import from ``reflex_base.constants`` at module level
    without creating a circular import for downstream code that imports
    ``reflex_base.utils.imports`` directly.
    """
    subprocess.run(
        [sys.executable, "-c", "import reflex_base.utils.imports"],
        check=True,
    )


def test_legacy_specifiers_match_frontend_package_constants():
    """The literal legacy-specifier targets stay in sync with the constants."""
    known_targets = {
        value
        for key, value in vars(constants.FrontendPackage).items()
        if key.isupper() and isinstance(value, str)
    }
    for old, new in LEGACY_FRONTEND_SPECIFIERS.items():
        assert new in known_targets, f"{old} maps to unknown specifier {new}"
        assert old.startswith("$/")
    assert LEGACY_FRONTEND_SPECIFIERS["$/utils/state"] == (
        constants.FrontendPackage.STATE
    )
    assert LEGACY_FRONTEND_SPECIFIERS["$/utils/state.js"] == (
        constants.FrontendPackage.STATE
    )


def test_merge_imports_normalizes_legacy_specifiers():
    """Old-style user import declarations land on the package specifier."""
    merged = merge_imports(
        {"$/utils/state": ["refs"]},
        {"/utils/state": ["isTrue"]},
        {constants.FrontendPackage.STATE: ["pyOr"]},
    )
    assert set(merged) == {constants.FrontendPackage.STATE}
    assert {var.tag for var in merged[constants.FrontendPackage.STATE]} == {
        "refs",
        "isTrue",
        "pyOr",
    }
