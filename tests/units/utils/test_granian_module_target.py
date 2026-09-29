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
    if installed:
        from reflex_base.config import Config

        config = Config(app_name="myapp", app_module_import=module)
        monkeypatch.setattr(exec_utils, "get_config", lambda: config)
    else:
        monkeypatch.setattr(exec_utils, "get_app_module", lambda: module)

    target, _ = exec_utils.get_app_instance_from_file().split(":", 1)
    assert prepare_import(target) == module
    sys.modules.pop(module, None)
    assert importlib.import_module(target).app is not None
    assert not (module_file.parent / "__init__.py").exists()
