"""Tests for development backend launchers in ``reflex.utils.exec``."""

import builtins
import logging
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
from reflex_base.utils.decorator import once

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


@pytest.mark.parametrize("deflate", [True, False])
def test_run_uvicorn_backend_passes_the_socket_policy(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    deflate: bool,
):
    """The dev server gets the app's websocket size and compression settings."""
    monkeypatch.setenv("REFLEX_SOCKET_PER_MESSAGE_DEFLATE", str(deflate).lower())
    mocker.patch.object(
        exec_utils,
        "get_dev_backend_reload_marker",
        return_value=tmp_path / exec_utils.DEV_BACKEND_RELOAD_MARKER,
    )
    mocker.patch.object(exec_utils, "get_app_instance", return_value="app:app")
    mocker.patch.object(exec_utils, "get_reload_paths", return_value=[])
    uvicorn = pytest.importorskip("uvicorn")
    run = mocker.patch.object(uvicorn, "run")

    exec_utils.run_uvicorn_backend(
        host="0.0.0.0", port=8000, loglevel=exec_utils.LogLevel.INFO
    )

    kwargs = run.call_args.kwargs
    assert kwargs["ws_per_message_deflate"] is deflate
    assert kwargs["ws_max_size"] == exec_utils._uvicorn_ws_max_size()


@pytest.mark.parametrize("deflate", [True, False])
def test_uvicorn_websocket_args_match_the_options(
    monkeypatch: pytest.MonkeyPatch, deflate: bool
):
    """Uvicorn's own CLI accepts the args, and reads the same policy from them.

    The Windows production backend passes these on a command line, where a
    misspelled option is not a wrong setting but a server that refuses to
    start, so they are checked against uvicorn's parser rather than a
    hand-written expectation.
    """
    pytest.importorskip("uvicorn")
    from uvicorn.main import main as uvicorn_cli

    monkeypatch.setenv("REFLEX_SOCKET_PER_MESSAGE_DEFLATE", str(deflate).lower())
    options = exec_utils.uvicorn_websocket_options()

    context = uvicorn_cli.make_context(
        "uvicorn", [*exec_utils._uvicorn_websocket_args(), "app:app"]
    )

    assert context.params["ws_per_message_deflate"] is deflate
    assert "--no-ws-per-message-deflate" not in exec_utils._uvicorn_websocket_args()
    assert context.params["ws_max_size"] == options["ws_max_size"]


def test_uvicorn_worker_carries_the_socket_policy(monkeypatch: pytest.MonkeyPatch):
    """The gunicorn worker class applies the settings gunicorn cannot pass on."""
    pytest.importorskip("gunicorn")
    pytest.importorskip("uvicorn")
    monkeypatch.setenv("REFLEX_SOCKET_PER_MESSAGE_DEFLATE", "false")
    # The class body reads the environment at import time.
    sys.modules.pop("reflex.utils.uvicorn_worker", None)
    from reflex.utils.uvicorn_worker import ReflexUvicornWorker

    assert (
        ReflexUvicornWorker.CONFIG_KWARGS.items()
        >= exec_utils.uvicorn_websocket_options().items()
    )
    assert ReflexUvicornWorker.CONFIG_KWARGS["ws_per_message_deflate"] is False


@pytest.fixture
def fresh_uvicorn_warnings(mocker: MockerFixture) -> None:
    """Give each test its own `once` caches for the uvicorn warnings.

    They are cached for the life of the process, so a warning another test
    already triggered would otherwise silently not be emitted again.
    """
    for name in ("_warn_about_uvicorn_websockets", "_warn_user_about_uvicorn"):
        warned = getattr(exec_utils, name)
        # Re-wrapping would paper over a dropped `once`, so require it first:
        # a single run asks `should_use_granian()` several times.
        assert hasattr(warned, "__wrapped__"), f"{name} must stay `once`-cached"
        mocker.patch.object(exec_utils, name, once(warned.__wrapped__))


def test_auto_detected_uvicorn_is_announced_once(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
    fresh_uvicorn_warnings: None,
):
    """A single run asks repeatedly; the notice belongs in the log once."""
    monkeypatch.delenv("REFLEX_USE_GRANIAN", raising=False)
    mocker.patch.object(
        exec_utils.importlib.util, "find_spec", side_effect=lambda name: object()
    )

    with caplog.at_level(logging.WARNING):
        assert exec_utils.should_use_granian() is False
        assert exec_utils.should_use_granian() is False

    assert caplog.text.count("This behavior will change in 0.8.0") == 1


@pytest.mark.parametrize("use_granian", ["0", "1"])
def test_forcing_uvicorn_warns_about_a_missing_websocket_library(
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
    fresh_uvicorn_warnings: None,
    use_granian: str,
):
    """Choosing uvicorn explicitly still reports that it cannot serve websockets.

    That choice is the likeliest way to end up without a websocket library, so
    the diagnostic cannot live only on the branch that auto-detects uvicorn.
    """
    monkeypatch.setenv("REFLEX_USE_GRANIAN", use_granian)
    mocker.patch.object(
        exec_utils.importlib.util,
        "find_spec",
        side_effect=lambda name: (
            None if name in ("websockets", "wsproto") else object()
        ),
    )

    with caplog.at_level(logging.WARNING):
        assert exec_utils.should_use_granian() is (use_granian == "1")

    warned = "has no websocket protocol library" in caplog.text
    assert warned is (use_granian == "0")
