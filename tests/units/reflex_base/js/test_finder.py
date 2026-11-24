"""Tests for finding the JavaScript modules an app imports from Python."""

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from reflex_base.js.modules import _app_modules, _JsFunction, _ScriptModule


def test_importing_a_module_registers_it(app_package: Path):
    """A JavaScript, TypeScript, JSX or TSX module of the app imports, and the compiler finds it.

    It holds the names Python looked up, for the compiler to check.

    Args:
        app_package: the app package, on sys.path.
    """
    party = importlib.import_module("js_app.party")
    assert party.__spec__ is not None
    assert party.__spec__.origin == str(app_package / "party.js")
    from js_app.counter import count  # pyright: ignore[reportMissingImports]
    from js_app.typed import typed  # pyright: ignore[reportMissingImports]
    from js_app.widget import show  # pyright: ignore[reportMissingImports]

    assert (typed, show, count) == (
        _JsFunction("js_app.typed", "typed"),
        _JsFunction("js_app.widget", "show"),
        _JsFunction("js_app.counter", "count"),
    )
    assert _app_modules() == {
        "js_app.party": _ScriptModule(app_package / "party.js"),
        "js_app.typed": _ScriptModule(app_package / "typed.ts", {"typed"}),
        "js_app.widget": _ScriptModule(app_package / "widget.jsx", {"show"}),
        "js_app.counter": _ScriptModule(app_package / "counter.tsx", {"count"}),
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
    """A Python module shadows a script of its name.

    Args:
        app_package: the app package, on sys.path.
    """
    (app_package / "both.py").write_text("VALUE = 'python'\n")
    (app_package / "both.js").write_text("export function VALUE() {}\n")
    assert importlib.import_module("js_app.both").VALUE == "python"


def test_a_directory_without_init_does_not_hide_a_script(app_package: Path):
    """A directory of the script's name without ``__init__.py`` is not a Python module.

    Args:
        app_package: the app package, on sys.path.
    """
    (app_package / "party").mkdir()
    (app_package / "party" / "bg.png").write_bytes(b"")
    from js_app.party import celebrate  # pyright: ignore[reportMissingImports]

    assert celebrate == _JsFunction("js_app.party", "celebrate")


def _load_config(project: Path, rxconfig_imports: str) -> subprocess.CompletedProcess:
    """Load the config of a project whose rxconfig.py imports a module.

    Args:
        project: The project's directory.
        rxconfig_imports: The import statement rxconfig.py starts with.

    Returns:
        The process that loaded it and printed the app's name.
    """
    (project / "rxconfig.py").write_text(
        f"import reflex as rx\n\n{rxconfig_imports}\n\n"
        "config = rx.Config(app_name='js_app', plugins=[], telemetry_enabled=False)\n"
    )
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from reflex_base.config import get_config; print(get_config().app_name)",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_script_imported_while_the_config_loads_is_not_found(tmp_path: Path):
    """A script is not found while rxconfig.py loads: its package is not known yet.

    Loading the config to know it would run rxconfig.py again inside itself.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    app = tmp_path / "js_app"
    app.mkdir()
    (app / "__init__.py").write_text("")
    (app / "settings.py").write_text("from js_app.party import go\n\nTITLE = 'x'\n")
    (app / "party.js").write_text("export function go() {}\n")
    loaded = _load_config(tmp_path, "from js_app.settings import TITLE")
    assert loaded.returncode == 1
    assert loaded.stderr.splitlines()[-1] == (
        "ModuleNotFoundError: No module named 'js_app.party'"
    )


def test_an_import_that_may_fail_still_fails_while_the_config_loads(tmp_path: Path):
    """A library that falls back when an import fails, beside a script of its name, loads.

    Args:
        tmp_path: pytest tmp_path fixture.
    """
    library = tmp_path / "optlib"
    library.mkdir()
    (library / "__init__.py").write_text(
        "try:\n    from optlib import speedups\nexcept ImportError:\n"
        "    speedups = None\n\nVERSION = '1.0'\n"
    )
    (library / "speedups.js").write_text("export function go() {}\n")
    loaded = _load_config(tmp_path, "from optlib import VERSION")
    assert (loaded.returncode, loaded.stdout) == (0, "js_app\n"), loaded.stderr


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
