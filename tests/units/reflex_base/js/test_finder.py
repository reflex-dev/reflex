"""Tests for finding the JavaScript modules an app imports from Python."""

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from reflex_base.js.modules import _JsFunction
from reflex_base.registry import RegistrationContext


def test_importing_a_module_exposes_its_functions(
    app_package: Path, clean_registration_context: RegistrationContext
):
    """A JavaScript or TypeScript module of the app imports, and is registered.

    Args:
        app_package: the app package, on sys.path.
        clean_registration_context: the registry the import fills.
    """
    party = importlib.import_module("js_app.party")
    assert party.__all__ == ["celebrate", "load", "arrow"]
    assert [party.celebrate, party.load, party.arrow] == [
        _JsFunction("js_app.party", "celebrate"),
        _JsFunction("js_app.party", "load"),
        _JsFunction("js_app.party", "arrow"),
    ]
    assert party.__spec__ is not None
    assert party.__spec__.origin == str(app_package / "party.js")
    typed = importlib.import_module("js_app.typed")
    assert typed.typed == _JsFunction("js_app.typed", "typed")
    assert clean_registration_context._script_modules == {
        "js_app.party": app_package / "party.js",
        "js_app.typed": app_package / "typed.ts",
    }


def test_only_the_app_package_is_searched(
    app_package: Path, clean_registration_context: RegistrationContext
):
    """Another package's JavaScript files are never imported or registered.

    Args:
        app_package: the app package, on sys.path.
        clean_registration_context: the registry an import would fill.
    """
    assert importlib.util.find_spec("js_vendor.widget") is None
    with pytest.raises(ModuleNotFoundError) as error:
        importlib.import_module("js_vendor.widget")
    assert str(error.value) == "No module named 'js_vendor.widget'"
    assert clean_registration_context._script_modules == {}


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
