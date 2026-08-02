"""Tests for development backend launchers in ``reflex.utils.exec``."""

import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base.environment import environment

from reflex.utils import exec as exec_utils

DEV_BACKEND_RELOAD_ENV_NAME = environment.REFLEX_DEV_BACKEND_RELOAD_ACTIVE.name
USE_GRANIAN_ENV_NAME = environment.REFLEX_USE_GRANIAN.name


def test_should_use_granian_by_default(monkeypatch: pytest.MonkeyPatch):
    """Granian is used when REFLEX_USE_GRANIAN is unset, even if Uvicorn is installed."""
    monkeypatch.delenv(USE_GRANIAN_ENV_NAME, raising=False)

    assert exec_utils.should_use_granian() is True


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_should_use_granian_when_enabled(value: str, monkeypatch: pytest.MonkeyPatch):
    """Granian is used when REFLEX_USE_GRANIAN is explicitly enabled."""
    monkeypatch.setenv(USE_GRANIAN_ENV_NAME, value)

    assert exec_utils.should_use_granian() is True


def test_should_not_use_granian_when_disabled_and_packages_installed(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """The Uvicorn/Gunicorn backend is used when opted in and its packages exist."""
    monkeypatch.setenv(USE_GRANIAN_ENV_NAME, "0")
    find_spec = mocker.patch.object(
        exec_utils.importlib.util, "find_spec", return_value=object()
    )

    assert exec_utils.should_use_granian() is False
    assert find_spec.call_count > 0


def test_should_use_granian_disabled_with_missing_packages_raises(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """Opting out of Granian without the required packages fails with an error."""
    monkeypatch.setenv(USE_GRANIAN_ENV_NAME, "0")
    mocker.patch.object(exec_utils.importlib.util, "find_spec", return_value=None)

    with pytest.raises(SystemExit):
        exec_utils.should_use_granian()


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
