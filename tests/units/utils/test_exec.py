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
from typing import Any
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
    exec_utils.get_app_instance_from_file = lambda: "reload_app:app"  # ty:ignore[invalid-assignment]
    exec_utils.get_reload_paths = lambda: [app_path]  # ty:ignore[invalid-assignment]
    exec_utils.get_dev_backend_reload_marker = lambda: app_path / ".reload"  # ty:ignore[invalid-assignment]
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
    server._init_shared_socket()  # ty:ignore[unresolved-attribute]
    listener: socket.socket = server._sso  # ty:ignore[unresolved-attribute]
    try:
        assert listener.get_inheritable()
        # Once a worker calls listen the supervisor's descriptor keeps the
        # socket listening, so connections queue while no worker accepts.
        listener.listen()
        with socket.create_connection(listener.getsockname(), timeout=1):
            pass
    finally:
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


@pytest.mark.parametrize("json_mode", [False, True])
def test_run_granian_backend_json_logs_in_json_mode(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    json_mode: bool,
):
    """Granian lifecycle logs are emitted as JSON records in JSON mode."""
    monkeypatch.setenv(environment.REFLEX_LOG_JSON.name, str(json_mode))
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
    options: dict[str, object] = {}

    class FakeGranian:
        def __init__(self, *_args, **kwargs):
            options.update(kwargs)

        def on_reload(self, _callback):
            pass

        def serve(self):
            pass

    mocker.patch.object(granian_server, "Server", FakeGranian)

    exec_utils.run_granian_backend(
        host="127.0.0.1", port=8000, loglevel=exec_utils.LogLevel.DEBUG
    )

    assert options["log_dictconfig"] == (
        {
            "handlers": {
                "console": {"()": "reflex_base.utils.log.JsonHandler"},
                "access": {"()": "reflex_base.utils.log.JsonHandler"},
            }
        }
        if json_mode
        else None
    )


@pytest.mark.parametrize("json_mode", [False, True])
def test_run_granian_backend_prod_json_logs_in_json_mode(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    json_mode: bool,
):
    """The production Granian path follows the same JSON stdout contract."""
    monkeypatch.setenv(environment.REFLEX_LOG_JSON.name, str(json_mode))
    mocker.patch.object(
        exec_utils, "get_app_instance_from_file", return_value="app:app"
    )
    mocker.patch.object(exec_utils, "_get_backend_workers", return_value=1)
    granian_server = pytest.importorskip("granian.server")
    options: dict[str, object] = {}

    class FakeGranian:
        def __init__(self, *_args, **kwargs):
            options.update(kwargs)

        def serve(self):
            pass

    mocker.patch.object(granian_server, "Server", FakeGranian)

    exec_utils.run_granian_backend_prod(
        host="127.0.0.1", port=8000, loglevel=exec_utils.LogLevel.DEBUG
    )

    assert options["log_dictconfig"] == (
        {
            "handlers": {
                "console": {"()": "reflex_base.utils.log.JsonHandler"},
                "access": {"()": "reflex_base.utils.log.JsonHandler"},
            }
        }
        if json_mode
        else None
    )


def _free_port() -> int:
    """Pick a TCP port that is currently unused.

    Returns:
        A free port on the loopback interface.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _port_is_bindable(port: int) -> bool:
    """Report whether a port is free to bind, i.e. nothing is listening on it.

    Args:
        port: The TCP port to check.

    Returns:
        Whether the port could be bound.
    """
    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", port))
    except OSError:
        return False
    else:
        return True
    finally:
        probe.close()


def _dev_granian_supervisor(mocker: MockerFixture, tmp_path: Path, port: int):
    """Build the dev Granian supervisor on top of a stand-in granian server.

    Args:
        mocker: The mocker fixture.
        tmp_path: Directory holding the reload marker.
        port: The TCP port the supervisor binds.

    Returns:
        The supervisor instance created by ``run_granian_backend``.
    """
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
    servers: list[Any] = []

    class FakeWorker:
        def __init__(self):
            self.interrupt_by_parent = False
            self.alive = True

        def _watcher(self):
            """Stand in for granian's watcher body, which joins the process."""

        def is_alive(self):
            return self.alive

    class FakeGranian:
        def __init__(self, *_args, **kwargs):
            self.bind_addr = kwargs["address"]
            self.bind_port = kwargs["port"]
            self.backlog = 16
            self.wrks = []
            self.shutdowns = []
            self._ssp = self._shd = self._sfd = None
            self._sso: Any = None
            servers.append(self)

        def _spawn_worker(self, idx, target, callback_loader):
            return FakeWorker()

        def on_reload(self, _callback):
            pass

        def serve(self):
            pass

        def shutdown(self, exit_code=0):
            # Granian detaches the socket object while unlinking the pid file.
            self._sso.detach()
            self.shutdowns.append(exit_code)

    mocker.patch.object(granian_server, "Server", FakeGranian)
    exec_utils.run_granian_backend(
        host="127.0.0.1", port=port, loglevel=exec_utils.LogLevel.ERROR
    )
    (server,) = servers
    return server


def _spawn_supervisor_worker(server) -> Any:
    """Spawn a worker on the supervisor and register it like granian does.

    Args:
        server: The supervisor under test.

    Returns:
        The spawned worker.
    """
    worker = server._spawn_worker(idx=0, target=None, callback_loader=None)
    server.wrks.append(worker)
    return worker


def test_run_granian_backend_releases_socket_when_worker_dies(
    tmp_path: Path, mocker: MockerFixture
):
    """A worker that dies on its own leaves the port refusing connections."""
    port = _free_port()
    server = _dev_granian_supervisor(mocker, tmp_path, port)
    try:
        server._init_shared_socket()
        assert not _port_is_bindable(port)

        worker = _spawn_supervisor_worker(server)
        worker.alive = False
        worker._watcher()

        assert _port_is_bindable(port)
    finally:
        if server._sso is not None:
            server._sso.close()


def test_run_granian_backend_keeps_socket_across_worker_restart(
    tmp_path: Path, mocker: MockerFixture
):
    """A worker stopped by the supervisor keeps the port bound for its successor."""
    port = _free_port()
    server = _dev_granian_supervisor(mocker, tmp_path, port)
    try:
        server._init_shared_socket()
        worker = _spawn_supervisor_worker(server)
        worker.interrupt_by_parent = True
        worker.alive = False
        worker._watcher()

        assert not _port_is_bindable(port)
    finally:
        if server._sso is not None:
            server._sso.close()


def test_run_granian_backend_rebinds_socket_for_the_next_worker(
    tmp_path: Path, mocker: MockerFixture
):
    """The socket released by a dead worker is re-created for the next one."""
    port = _free_port()
    server = _dev_granian_supervisor(mocker, tmp_path, port)
    try:
        server._init_shared_socket()
        worker = _spawn_supervisor_worker(server)
        worker.alive = False
        worker._watcher()
        assert _port_is_bindable(port)

        _spawn_supervisor_worker(server)

        assert not _port_is_bindable(port)
        assert server._sso.get_inheritable()
    finally:
        if server._sso is not None:
            server._sso.close()


def test_run_granian_backend_releases_socket_on_shutdown(
    tmp_path: Path, mocker: MockerFixture
):
    """Shutting the supervisor down frees the port it holds."""
    port = _free_port()
    server = _dev_granian_supervisor(mocker, tmp_path, port)
    try:
        server._init_shared_socket()
        server.shutdown()

        assert _port_is_bindable(port)
        assert server.shutdowns == [0]
    finally:
        if server._sso is not None:
            server._sso.close()


def _wait_for_refused_connection(port: int, timeout: float = 20) -> bool:
    """Poll a port until it refuses a connection.

    Args:
        port: TCP port for the test server.
        timeout: Seconds to keep polling.

    Returns:
        Whether the port refused a connection within the timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass
        except ConnectionRefusedError:
            return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


def _wait_for_ok_response(port: int, timeout: float = 20) -> bool:
    """Poll a port until the test app answers it.

    Args:
        port: TCP port for the test server.
        timeout: Seconds to keep polling.

    Returns:
        Whether the app answered with a 200 within the timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if _request_reload_test_app(port)[0] == 200:
                return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


@pytest.mark.skipif(sys.platform != "linux", reason="Granian uses this path on Linux")
def test_run_granian_backend_refuses_requests_while_the_app_is_broken(tmp_path: Path):
    """A module that raises on import makes requests fail fast, then recover."""
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
        assert _wait_for_ok_response(port), "Granian did not start"

        app_file.write_text('raise RuntimeError("broken test app")\n')
        assert _wait_for_refused_connection(port), (
            "the backend port kept accepting connections with no worker to serve them"
        )

        app_file.write_text(_reload_test_app_source(0))
        assert _wait_for_ok_response(port), "the backend did not recover"
    finally:
        process.terminate()
        process.join(timeout=10)
        if process.is_alive():
            process.kill()
            process.join()
        port_queue.close()
