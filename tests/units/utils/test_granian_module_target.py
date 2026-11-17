"""Regression for a backend app whose package has no __init__.py."""

import importlib
import sys
from pathlib import Path

import pytest

from reflex.utils import exec as exec_utils

APP_SOURCE = "def app():\n    return 'asgi'\n"


def _load_worker_app() -> object:
    """Resolve and call the backend worker target the way granian does.

    Returns:
        The ASGI app the worker factory creates.
    """
    from granian._internal import prepare_import

    module, attr = exec_utils.get_app_instance_from_file().split(":", 1)
    assert prepare_import(module) == module
    return getattr(importlib.import_module(module), attr)()


@pytest.mark.parametrize("installed", [False, True])
def test_granian_target_keeps_configured_module_without_writing_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed: bool
):
    root = tmp_path / "installed" if installed else tmp_path
    module = "installed_app_7304" if installed else "myapp.myapp"
    module_file = root.joinpath(*module.split(".")).with_suffix(".py")
    module_file.parent.mkdir(parents=True)
    module_file.write_text(APP_SOURCE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(root))
    original_path = sys.path.copy()
    if installed:
        from reflex_base.config import Config

        config = Config(app_name="myapp", app_module_import=module)
        monkeypatch.setattr(exec_utils, "get_config", lambda: config)
    else:
        monkeypatch.setattr(exec_utils, "get_app_module", lambda: module)

    sys.modules.pop(module, None)
    try:
        assert _load_worker_app() == "asgi"
        assert not (module_file.parent / "__init__.py").exists()
    finally:
        sys.modules.pop(module, None)
        for index in range(1, len(module.split("."))):
            sys.modules.pop(".".join(module.split(".")[:index]), None)
        sys.path[:] = original_path


def test_granian_target_rejects_missing_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The module target still provides the existing missing-module error."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(exec_utils, "get_app_module", lambda: "missing.app")
    with pytest.raises(ImportError, match=r"Module missing\.app not found"):
        exec_utils.get_app_instance_from_file()


def test_granian_target_adds_project_root_to_sys_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An installed console script may not put the project root on sys.path."""
    app_dir = tmp_path / "local_app_7304"
    app_dir.mkdir()
    (app_dir / "app.py").write_text(APP_SOURCE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "path", [entry for entry in sys.path if entry != str(tmp_path)]
    )
    monkeypatch.setattr(exec_utils, "get_app_module", lambda: "local_app_7304.app")

    try:
        assert _load_worker_app() == "asgi"
    finally:
        sys.modules.pop("local_app_7304.app", None)
        sys.modules.pop("local_app_7304", None)
