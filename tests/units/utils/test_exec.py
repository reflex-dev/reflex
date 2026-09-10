"""Tests for development backend launchers in ``reflex.utils.exec``."""

import gc
import multiprocessing
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base.environment import environment

from reflex.utils import exec as exec_utils
from reflex.utils import prerequisites

DEV_BACKEND_RELOAD_ENV_NAME = environment.REFLEX_DEV_BACKEND_RELOAD_ACTIVE.name


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


def _fake_granian_prod(mocker: MockerFixture, calls: list[str]):
    """Patch granian and the prod launcher's collaborators, recording call order."""
    granian_server = pytest.importorskip("granian.server")

    class FakeGranian:
        def __init__(self, *_args, **_kwargs):
            pass

        def serve(self):
            calls.append("serve")

    mocker.patch.object(granian_server, "Server", FakeGranian)
    mocker.patch.object(
        exec_utils, "get_app_instance_from_file", return_value="app:app"
    )
    mocker.patch.object(exec_utils, "_get_backend_workers", return_value=1)
    mocker.patch.object(
        multiprocessing,
        "set_start_method",
        side_effect=lambda method, force=False: calls.append(f"start:{method}"),
    )
    mocker.patch.object(
        prerequisites, "get_app", side_effect=lambda: calls.append("preload")
    )
    mocker.patch.object(gc, "freeze", side_effect=lambda: calls.append("freeze"))


def test_run_granian_backend_prod_preloads_app_before_forking(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """With fork, the app is imported and the heap frozen before workers start."""
    monkeypatch.setenv(environment.REFLEX_BACKEND_START_METHOD.name, "fork")
    calls: list[str] = []
    _fake_granian_prod(mocker, calls)

    exec_utils.run_granian_backend_prod(
        host="0.0.0.0", port=8000, loglevel=exec_utils.LogLevel.INFO
    )

    assert calls == ["start:fork", "preload", "freeze", "serve"]


def test_run_granian_backend_prod_spawn_skips_preload(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """Spawned workers re-import the app, so the supervisor does not load it."""
    monkeypatch.setenv(environment.REFLEX_BACKEND_START_METHOD.name, "spawn")
    calls: list[str] = []
    _fake_granian_prod(mocker, calls)

    exec_utils.run_granian_backend_prod(
        host="0.0.0.0", port=8000, loglevel=exec_utils.LogLevel.INFO
    )

    assert calls == ["start:spawn", "serve"]


def test_run_granian_backend_prod_custom_target_only_freezes(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """A non-reflex target lives in an already-imported module."""
    monkeypatch.setenv(environment.REFLEX_BACKEND_START_METHOD.name, "fork")
    calls: list[str] = []
    _fake_granian_prod(mocker, calls)

    exec_utils.run_granian_backend_prod(
        host="0.0.0.0",
        port=8000,
        loglevel=exec_utils.LogLevel.INFO,
        app_target="reflex.utils.exec:_frontend_prod_app",
    )

    assert calls == ["start:fork", "freeze", "serve"]


@pytest.mark.parametrize(
    ("default_method", "expected"),
    [("fork", "fork"), ("forkserver", "fork"), ("spawn", None)],
)
def test_backend_start_method_follows_platform_default(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    default_method: str,
    expected: str | None,
):
    """Fork is forced only where the interpreter already defaults to forking."""
    monkeypatch.delenv(environment.REFLEX_BACKEND_START_METHOD.name, raising=False)
    mocker.patch.object(
        multiprocessing, "get_start_method", return_value=default_method
    )

    assert exec_utils._backend_start_method() == expected
