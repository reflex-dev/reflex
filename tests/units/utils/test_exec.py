"""Tests for development backend launchers in ``reflex.utils.exec``."""

import os
import socket
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base.environment import environment

from reflex.utils import exec as exec_utils

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


def test_run_granian_backend_binds_listen_socket_in_supervisor(
    tmp_path: Path, mocker: MockerFixture
):
    """The dev server holds the listen socket so requests queue across worker restarts."""
    mocker.patch.object(
        exec_utils,
        "get_dev_backend_reload_marker",
        return_value=tmp_path / exec_utils.DEV_BACKEND_RELOAD_MARKER,
    )
    mocker.patch.object(
        exec_utils, "get_app_instance_from_file", return_value="app:app"
    )
    mocker.patch.object(exec_utils, "get_reload_paths", return_value=[])
    granian_server = pytest.importorskip("granian.server")
    servers: list[object] = []

    class FakeGranian:
        def __init__(self, *_args, **_kwargs):
            self.bind_addr = "127.0.0.1"
            self.bind_port = 0
            self.backlog = 16
            servers.append(self)

        def on_reload(self, _callback):
            pass

        def serve(self):
            pass

    mocker.patch.object(granian_server, "Server", FakeGranian)

    exec_utils.run_granian_backend(
        host="127.0.0.1", port=0, loglevel=exec_utils.LogLevel.INFO
    )

    (server,) = servers
    server._init_shared_socket()  # pyright: ignore[reportAttributeAccessIssue]
    listener: socket.socket = server._sso  # pyright: ignore[reportAttributeAccessIssue]
    try:
        assert listener.get_inheritable()
        # Once a worker calls listen the supervisor's descriptor keeps the
        # socket listening, so connections queue while no worker accepts.
        listener.listen()
        with socket.create_connection(listener.getsockname(), timeout=1):
            pass
    finally:
        listener.close()


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
