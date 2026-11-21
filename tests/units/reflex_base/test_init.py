"""Tests for the module finder ``import reflex`` registers."""

import importlib
import subprocess
import sys

import reflex_base


def test_import_reflex_registers_one_finder_and_loads_nothing():
    """``import reflex`` registers the finder without loading a module for it.

    Importing it again, as a benchmark that clears ``sys.modules`` does, must
    not register a second one.
    """
    output = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib, sys\n"
                "import reflex\n"
                "for name in [n for n in sys.modules if n.startswith('reflex')]:\n"
                "    del sys.modules[name]\n"
                "importlib.import_module('reflex')\n"
                "finders = [f for f in sys.meta_path if getattr(f, '__qualname__', '') == '_ScriptFinder']\n"
                "print(len(finders), 'reflex_base.js' in sys.modules)"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert output == "1 False\n"


def test_reloading_registers_no_second_finder():
    """Reloading the package keeps the finder registered once."""
    finders = [f for f in sys.meta_path if f is reflex_base._ScriptFinder]
    assert len(finders) == 1
    importlib.reload(reflex_base)
    # The reload defines a new class; the registered one stays the only one.
    assert [
        f for f in sys.meta_path if getattr(f, "__qualname__", "") == "_ScriptFinder"
    ] == finders
