"""Tests for finding the JavaScript modules an app imports from Python."""

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from reflex_base.js.modules import _app_modules, _JsFunction, _ScriptModule


def test_importing_a_module_registers_it(app_package: Path):
    """A JavaScript or TypeScript module of the app imports, and the compiler finds it.

    It holds the names Python looked up, for the compiler to check.

    Args:
        app_package: the app package, on sys.path.
    """
    party = importlib.import_module("js_app.party")
    assert party.__spec__ is not None
    assert party.__spec__.origin == str(app_package / "party.js")
    from js_app.typed import typed  # pyright: ignore[reportMissingImports]

    assert typed == _JsFunction("js_app.typed", "typed")
    assert _app_modules() == {
        "js_app.party": _ScriptModule(app_package / "party.js"),
        "js_app.typed": _ScriptModule(app_package / "typed.ts", {"typed"}),
    }


def test_only_the_app_package_is_searched(app_package: Path):
    """Another package's JavaScript files are never imported.

    Args:
        app_package: the app package, on sys.path.
    """
    assert importlib.util.find_spec("js_vendor.widget") is None
    with pytest.raises(ModuleNotFoundError) as error:
        importlib.import_module("js_vendor.widget")
    assert str(error.value) == "No module named 'js_vendor.widget'"


def test_a_missing_module_still_fails_to_import(app_package: Path):
    """A name with neither a Python nor a JavaScript module still fails.

    Args:
        app_package: the app package, on sys.path.
    """
    with pytest.raises(ModuleNotFoundError) as error:
        importlib.import_module("js_app.missing")
    assert str(error.value) == "No module named 'js_app.missing'"


def test_a_python_module_wins_over_a_script_of_the_same_name(app_package: Path):
    """The finder runs last, so a Python module shadows a script of its name.

    Args:
        app_package: the app package, on sys.path.
    """
    (app_package / "both.py").write_text("VALUE = 'python'\n")
    (app_package / "both.js").write_text("export function VALUE() {}\n")
    assert importlib.import_module("js_app.both").VALUE == "python"


def test_the_finder_imports_nothing_heavy():
    """The finder loads on the first import no other finder found, so it stays cheap."""
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, reflex_base.js.finder; "
                "print(sorted({'pathlib', 'typing', 'importlib.abc', "
                "'reflex_base.config', 'reflex_base.event'} & set(sys.modules)))"
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert loaded == "[]\n"
