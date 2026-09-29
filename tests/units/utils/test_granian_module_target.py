"""Regression for a backend app whose package has no __init__.py."""

import importlib
import sys
from pathlib import Path

import pytest

from reflex.utils import exec as exec_utils


@pytest.mark.parametrize("installed", [False, True])
def test_granian_target_keeps_configured_module_without_writing_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed: bool
):
    from granian._internal import prepare_import

    root = tmp_path / "installed" if installed else tmp_path
    module = "installed_app_7304" if installed else "myapp.myapp"
    module_file = root.joinpath(*module.split(".")).with_suffix(".py")
    module_file.parent.mkdir(parents=True)
    module_file.write_text("app = object()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(root))
    original_path = sys.path.copy()
    if installed:
        from reflex_base.config import Config

        config = Config(app_name="myapp", app_module_import=module)
        monkeypatch.setattr(exec_utils, "get_config", lambda: config)
    else:
        monkeypatch.setattr(exec_utils, "get_app_module", lambda: module)

    target, _ = exec_utils.get_app_instance_from_file().split(":", 1)
    assert prepare_import(target) == module
    sys.modules.pop(module, None)
    try:
        assert importlib.import_module(target).app is not None
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
    monkeypatch.setattr(exec_utils, "get_app_module", lambda: "missing.app")
    with pytest.raises(ImportError, match=r"Module missing\.app not found"):
        exec_utils.get_app_instance_from_file()


def test_granian_target_adds_project_root_to_sys_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An installed console script may not put the project root on sys.path."""
    app_dir = tmp_path / "local_app_7304"
    app_dir.mkdir()
    (app_dir / "app.py").write_text("app = object()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys, "path", [entry for entry in sys.path if entry != str(tmp_path)]
    )
    monkeypatch.setattr(exec_utils, "get_app_module", lambda: "local_app_7304.app")

    target, _ = exec_utils.get_app_instance_from_file().split(":", 1)
    try:
        assert importlib.import_module(target).app is not None
    finally:
        sys.modules.pop(target, None)
        sys.modules.pop("local_app_7304", None)
