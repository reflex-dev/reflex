"""Tests for development backend launchers in ``reflex.utils.exec``."""

import builtins
import multiprocessing
import os
import socket
import sys
import time
from http.client import HTTPConnection
from multiprocessing.queues import Queue
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_mock import MockerFixture
from reflex_base.environment import environment
from reflex_base.utils import serializers

from reflex.utils import exec as exec_utils

DEV_BACKEND_RELOAD_ENV_NAME = environment.REFLEX_DEV_BACKEND_RELOAD_ACTIVE.name


def _run_granian_reload_test_app(app_dir: str, port_queue: Queue) -> None:
    """Run a reloadable Granian app in a child process.

    Args:
        app_dir: Directory containing the test app module.
        port_queue: Queue receiving the supervisor's selected TCP port.
    """
    app_path = Path(app_dir)
    sys.path.insert(0, app_dir)
    exec_utils.get_app_instance_from_file = lambda: "reload_app:app"
    exec_utils.get_reload_paths = lambda: [app_path]
    exec_utils.get_dev_backend_reload_marker = lambda: app_path / ".reload"
    original_socket = socket.socket

    def report_listener(*args, **kwargs):
        """Report the port of the supervisor-owned socket.

        Args:
            *args: Positional arguments forwarded to ``socket.socket``.
            **kwargs: Keyword arguments forwarded to ``socket.socket``.

        Returns:
            The created socket.
        """
        listener = original_socket(*args, **kwargs)
        if kwargs.get("fileno") is not None:
            port_queue.put(listener.getsockname()[1])
        return listener

    with patch.object(exec_utils.socket, "socket", side_effect=report_listener):
        exec_utils.run_granian_backend("127.0.0.1", 0, exec_utils.LogLevel.ERROR)


def _request_reload_test_app(port: int, timeout: float = 5) -> tuple[int, float]:
    """Request the reload test app and report its response time.

    Args:
        port: TCP port for the test server.
        timeout: Request timeout in seconds.

    Returns:
        The HTTP response status and elapsed request time in seconds.
    """
    started = time.monotonic()
    connection = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        response.read()
        return response.status, time.monotonic() - started
    finally:
        connection.close()


def _reload_test_app_source(startup_delay: float) -> str:
    """Build the ASGI test app source with an optional worker startup delay.

    Args:
        startup_delay: Seconds to sleep while the worker imports the app.

    Returns:
        Python source for the test app.
    """
    return f"""\
import time

time.sleep({startup_delay})


def app():
    async def asgi(scope, receive, send):
        await send({{"type": "http.response.start", "status": 200, "headers": []}})
        await send({{"type": "http.response.body", "body": b"ok"}})

    return asgi
"""


@pytest.mark.parametrize("frontend_present", [False, True])
def test_run_backend_manages_nocompile_marker(
    tmp_path: Path,
    mocker: MockerFixture,
    frontend_present: bool,
) -> None:
    """Only full-stack backend runs leave the compile-skip marker."""
    marker = tmp_path / exec_utils.constants.NOCOMPILE_FILE
    if not frontend_present:
        marker.touch()
    mocker.patch.object(exec_utils, "get_web_dir", return_value=tmp_path)
    mocker.patch.object(exec_utils, "should_use_granian", return_value=True)
    mocker.patch.object(exec_utils, "run_granian_backend")
    mocker.patch.object(exec_utils, "notify_backend")

    exec_utils.run_backend("127.0.0.1", 8000, frontend_present=frontend_present)

    assert marker.exists() is frontend_present


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
    prepare_fork = mocker.patch.object(serializers, "_prepare_serializers_for_fork")

    exec_utils.run_backend("127.0.0.1", 8000)

    run_granian.assert_called_once()
    prepare_fork.assert_not_called()


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
    prepare_fork = mocker.patch.object(serializers, "_prepare_serializers_for_fork")

    exec_utils.run_backend("127.0.0.1", 8000)

    assert imported == ["reflex.app"]
    prepare_fork.assert_called_once_with()


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
        # granian's SocketHolder in _shd co-owns the listener's OS handle: on
        # Windows dropping it closes the handle, elsewhere its Drop forgets it.
        # Settle ownership here so the handle is closed exactly once. Left to
        # the cyclic GC (FakeGranian sits in a reference cycle via `servers`),
        # the holder's late close would land on a reused handle in whatever
        # test happens to be running, e.g. an event loop's self-pipe socket.
        server._shd = None  # pyright: ignore[reportAttributeAccessIssue]
        if sys.platform == "win32":
            listener.detach()
        else:
            listener.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Granian uses this path on Linux")
def test_run_granian_backend_holds_requests_across_reload(tmp_path: Path):
    """Requests queue until a slow replacement worker finishes loading."""
    app_file = tmp_path / "reload_app.py"
    app_file.write_text(_reload_test_app_source(0))
    context = multiprocessing.get_context("spawn")
    port_queue: Queue = context.Queue()
    process = context.Process(
        target=_run_granian_reload_test_app,
        args=(str(tmp_path), port_queue),
    )
    process.start()
    try:
        port = port_queue.get(timeout=20)
        deadline = time.monotonic() + 20
        while True:
            try:
                assert _request_reload_test_app(port)[0] == 200
                break
            except OSError:
                assert time.monotonic() < deadline, "Granian did not start"
                time.sleep(0.05)

        app_file.write_text(_reload_test_app_source(1.0))
        responses: list[tuple[int, float]] = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            responses.append(_request_reload_test_app(port))
            if responses[-1][1] > 0.5:
                break
            time.sleep(0.05)

        assert all(status == 200 for status, _ in responses)
        assert any(elapsed > 0.5 for _, elapsed in responses)
    finally:
        process.terminate()
        process.join(timeout=10)
        if process.is_alive():
            process.kill()
            process.join()
        port_queue.close()


def test_frontend_env_defaults_mimalloc_and_no_color():
    """The toolchain env disables eager arena commit unless the user set it."""
    env = exec_utils.frontend_env({"PATH": "/bin"})
    assert env == {
        "PATH": "/bin",
        "MIMALLOC_ARENA_EAGER_COMMIT": "0",
        "NO_COLOR": "1",
    }
    assert (
        exec_utils.frontend_env({"MIMALLOC_ARENA_EAGER_COMMIT": "1"})[
            "MIMALLOC_ARENA_EAGER_COMMIT"
        ]
        == "1"
    )


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
