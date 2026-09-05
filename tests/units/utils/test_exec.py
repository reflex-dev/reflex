"""Tests for development backend launchers in ``reflex.utils.exec``."""

import builtins
import multiprocessing
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base.environment import environment

from reflex.utils import exec as exec_utils

DEV_BACKEND_RELOAD_ENV_NAME = environment.REFLEX_DEV_BACKEND_RELOAD_ACTIVE.name


def test_run_backend_skips_app_preload_for_spawn(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spawned Granian workers cannot reuse modules imported by the supervisor."""
    mocker.patch.object(exec_utils, "get_web_dir", return_value=tmp_path)
    mocker.patch.object(exec_utils, "should_use_granian", return_value=True)
    run_granian = mocker.patch.object(exec_utils, "run_granian_backend")
    mocker.patch.object(exec_utils, "notify_backend")
    mocker.patch.object(multiprocessing, "get_start_method", return_value="spawn")
    monkeypatch.setenv(environment.REFLEX_STRICT_HOT_RELOAD.name, "False")

    real_import = builtins.__import__

    def import_without_app_preload(name, *args, **kwargs):
        if name == "reflex.app":
            msg = "reflex.app was preloaded in a spawn-based supervisor"
            raise AssertionError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_app_preload)

    exec_utils.run_backend("127.0.0.1", 8000)

    run_granian.assert_called_once()


def test_run_backend_preloads_app_for_fork(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forked Granian workers reuse the supervisor's imported app modules."""
    mocker.patch.object(exec_utils, "get_web_dir", return_value=tmp_path)
    mocker.patch.object(exec_utils, "should_use_granian", return_value=True)
    mocker.patch.object(exec_utils, "run_granian_backend")
    mocker.patch.object(exec_utils, "notify_backend")
    mocker.patch.object(multiprocessing, "get_start_method", return_value="fork")
    monkeypatch.setenv(environment.REFLEX_STRICT_HOT_RELOAD.name, "False")

    imported: list[str] = []
    real_import = builtins.__import__

    def track_app_preload(name, *args, **kwargs):
        if name == "reflex.app":
            imported.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", track_app_preload)

    exec_utils.run_backend("127.0.0.1", 8000)

    assert imported == ["reflex.app"]


def test_run_uvicorn_backend_sets_reload_env_var_and_clears_marker(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """``run_uvicorn_backend`` initializes reload worker process context."""
    marker = tmp_path / exec_utils.DEV_BACKEND_RELOAD_MARKER
    marker.touch()
    monkeypatch.delenv(DEV_BACKEND_RELOAD_ENV_NAME, raising=False)
    mocker.patch.object(
        exec_utils, "get_dev_backend_reload_marker", return_value=marker
    )
    mocker.patch.object(exec_utils, "get_app_instance", return_value="app:app")
    mocker.patch.object(exec_utils, "get_reload_paths", return_value=[])

    seen: dict[str, str | None] = {}

    def fake_run(*_args, **_kwargs):
        seen["value"] = os.environ.get(DEV_BACKEND_RELOAD_ENV_NAME)
        assert not marker.exists()

    uvicorn = pytest.importorskip("uvicorn")
    mocker.patch.object(uvicorn, "run", side_effect=fake_run)

    exec_utils.run_uvicorn_backend(
        host="0.0.0.0", port=8000, loglevel=exec_utils.LogLevel.INFO
    )

    assert seen["value"] == "True"


def test_run_granian_backend_sets_reload_env_var_and_clears_marker(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """``run_granian_backend`` initializes reload worker process context."""
    marker = tmp_path / exec_utils.DEV_BACKEND_RELOAD_MARKER
    marker.touch()
    monkeypatch.delenv(DEV_BACKEND_RELOAD_ENV_NAME, raising=False)
    mocker.patch.object(
        exec_utils, "get_dev_backend_reload_marker", return_value=marker
    )
    mocker.patch.object(
        exec_utils, "get_app_instance_from_file", return_value="app:app"
    )
    mocker.patch.object(exec_utils, "get_reload_paths", return_value=[])

    seen: dict[str, str | None] = {}

    granian_server = pytest.importorskip("granian.server")

    class FakeGranian:
        def __init__(self, *_args, **_kwargs):
            seen["value"] = os.environ.get(DEV_BACKEND_RELOAD_ENV_NAME)
            assert not marker.exists()

        def on_reload(self, _callback):
            pass

        def serve(self):
            pass

    mocker.patch.object(granian_server, "Server", FakeGranian)

    exec_utils.run_granian_backend(
        host="0.0.0.0", port=8000, loglevel=exec_utils.LogLevel.INFO
    )

    assert seen["value"] == "True"


def test_with_development_condition_sets_node_and_bun_options():
    """Both runtime option vars gain the development condition flag."""
    env = exec_utils._with_development_condition({})
    assert env["NODE_OPTIONS"] == "--conditions=development"
    assert env["BUN_OPTIONS"] == "--conditions=development"


def test_with_development_condition_preserves_existing_options():
    """Existing runtime options are kept, the flag is appended once, and the
    base environment is not mutated.
    """
    environ = {
        "NODE_OPTIONS": "--max-old-space-size=4096",
        "BUN_OPTIONS": "--conditions=development",
    }
    env = exec_utils._with_development_condition(environ)
    assert env["NODE_OPTIONS"] == "--max-old-space-size=4096 --conditions=development"
    # Already-present flag is not duplicated.
    assert env["BUN_OPTIONS"] == "--conditions=development"
    # The dev condition must not leak into the parent environment.
    assert environ["NODE_OPTIONS"] == "--max-old-space-size=4096"


def test_arbitrate_ssr_stores_flag_when_env_unset(monkeypatch: pytest.MonkeyPatch):
    """The flag value is stored in the environment when REFLEX_SSR is unset."""
    monkeypatch.setenv(environment.REFLEX_SSR.name, "")

    assert exec_utils.arbitrate_ssr(False) is False
    assert environment.REFLEX_SSR.get() is False


def test_arbitrate_ssr_env_var_wins(monkeypatch: pytest.MonkeyPatch):
    """An already-set REFLEX_SSR env var overrides the flag value."""
    monkeypatch.setenv(environment.REFLEX_SSR.name, "False")

    assert exec_utils.arbitrate_ssr(True) is False
