"""Unit tests for the included testing tools."""

import asyncio
import contextlib
import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator
from types import ModuleType, SimpleNamespace
from unittest import mock

import httpx
import pytest
import reflex_base.config
from reflex_base.components.memo import MEMOS
from reflex_base.constants import IS_WINDOWS
from reflex_base.environment import environment
from reflex_base.registry import RegistrationContext
from reflex_base.utils.types import ASGIApp
from starlette.applications import Starlette

import reflex.constants
import reflex.reflex as reflex_cli
import reflex.testing as reflex_testing
import reflex.utils.prerequisites
from reflex.testing import AppHarness
from reflex.utils.exec import should_prerender_routes


def test_testing_module_does_not_import_uvicorn_at_module_load():
    """Importing reflex.testing does not require the AppHarness backend runtime."""
    assert "uvicorn" not in reflex_testing.__dict__


@pytest.mark.skip("Slow test that makes network requests.")
def test_app_harness(tmp_path):
    """Ensure that AppHarness can compile and start an app.

    Args:
        tmp_path: pytest tmp_path fixture
    """
    # Skip in Windows CI.
    if IS_WINDOWS:
        return

    def BasicApp():
        import reflex as rx

        class State(rx.State):
            pass

        app = rx.App(_state=State)
        app.add_page(lambda: rx.text("Basic App"), route="/", title="index")
        app._compile()

    with AppHarness.create(
        root=tmp_path,
        app_source=BasicApp,
    ) as harness:
        assert harness.app_instance is not None
        assert harness.backend is not None
        assert harness.frontend_url is not None
        assert harness.frontend_process is not None
        assert harness.frontend_process.poll() is None

    assert harness.frontend_process.poll() is not None


@pytest.fixture
def harness_mocks(monkeypatch):
    """Common mocks for AppHarness initialization tests.

    Args:
        monkeypatch: pytest monkeypatch fixture

    Returns:
        Namespace with fake_config and get_and_validate_app mock.
    """
    fake_config = SimpleNamespace(loglevel=None, module="test_app.test_app")
    fake_app = mock.Mock(_state_manager=None)
    get_and_validate_app = mock.Mock(
        return_value=reflex.utils.prerequisites.AppInfo(
            app=fake_app,
            module=ModuleType(fake_config.module),
        )
    )

    monkeypatch.setattr(reflex_testing, "get_config", lambda: fake_config)
    monkeypatch.setattr(reflex_testing, "reload_config", lambda: fake_config)
    monkeypatch.setattr(reflex_base.config, "get_config", lambda: fake_config)
    monkeypatch.setattr(reflex_base.config, "reload_config", lambda: fake_config)
    monkeypatch.setattr(
        reflex.utils.prerequisites,
        "get_and_validate_app",
        get_and_validate_app,
    )

    return SimpleNamespace(
        config=fake_config,
        get_and_validate_app=get_and_validate_app,
    )


def test_app_harness_initialize_isolates_memo_registries(
    tmp_path, harness_mocks, monkeypatch
):
    """Each AppHarness initialization yields a fresh registration context.

    The global memo registry is also cleared so entries registered by a prior
    app do not leak into the new harness's registrations.

    Args:
        tmp_path: pytest tmp_path fixture
        harness_mocks: shared AppHarness mock setup
        monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setattr(reflex_cli, "_init", lambda **kwargs: None)

    outer = RegistrationContext.ensure_context()
    # Pin a clean base so pollution on the outer context does not seed new harnesses.
    base = RegistrationContext()
    monkeypatch.setattr(AppHarness, "_base_registration_context", base)

    MEMOS["format_value", None] = mock.sentinel.memo

    harness = AppHarness.create(
        root=tmp_path / "memo_app",
        app_source="import reflex as rx\napp = rx.App()",
        app_name="memo_app",
    )
    harness.app_module_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        harness._initialize_app()

        new_ctx = RegistrationContext.get()
        assert new_ctx is not outer
        assert ("format_value", None) not in MEMOS
        harness_mocks.get_and_validate_app.assert_called_once_with(reload=True)
    finally:
        # `_initialize_app` attaches a new context without a matching __exit__.
        # Restore the outer context so other tests do not observe the leaked one.
        if harness._registry_token is not None:
            RegistrationContext.reset(harness._registry_token)


def test_app_harness_initialize_resets_leaked_prod_env_mode(
    tmp_path, preserve_memo_registries, harness_mocks, monkeypatch
):
    """A leaked prod REFLEX_ENV_MODE must not affect the next dev harness.

    ``AppHarnessProd`` runs ``export()``, which sets ``REFLEX_ENV_MODE=prod``
    process-wide and never restores it. A dev ``AppHarness`` compiling later in
    the same process would then write ``prerender: true`` into its dev
    react-router config, making the dev server serve prerendered page HTML
    whose hydration failures break event delivery.

    Args:
        tmp_path: pytest tmp_path fixture
        preserve_memo_registries: restores global memo registries after the test
        harness_mocks: shared AppHarness mock setup
        monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setattr(reflex_cli, "_init", lambda **kwargs: None)
    monkeypatch.setenv("REFLEX_ENV_MODE", reflex.constants.Env.PROD.value)

    harness = AppHarness.create(
        root=tmp_path / "env_mode_app",
        app_source="import reflex as rx\napp = rx.App()",
        app_name="env_mode_app",
    )
    harness.app_module_path.parent.mkdir(parents=True, exist_ok=True)
    harness._initialize_app()

    assert environment.REFLEX_ENV_MODE.get() == reflex.constants.Env.DEV
    assert not should_prerender_routes()


def test_app_harness_initialize_reloads_existing_imported_app(
    tmp_path, harness_mocks, monkeypatch
):
    """Ensure pre-existing imported apps are reloaded after memo registry reset.

    Args:
        tmp_path: pytest tmp_path fixture
        harness_mocks: shared AppHarness mock setup
        monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setattr(
        reflex.utils.prerequisites,
        "initialize_frontend_dependencies",
        lambda: None,
    )
    monkeypatch.setitem(
        sys.modules,
        harness_mocks.config.module,
        ModuleType(harness_mocks.config.module),
    )

    harness = AppHarness.create(root=tmp_path / "plain_app")
    harness._initialize_app()

    harness_mocks.get_and_validate_app.assert_called_once_with(reload=True)


def _asgi_app(on_startup: Callable[[], object] | None = None) -> ASGIApp:
    """A minimal ASGI app with lifespan support that answers every request.

    Args:
        on_startup: called (in a worker thread) during lifespan startup.

    Returns:
        The ASGI app.
    """

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while (await receive())["type"] == "lifespan.startup":
                if on_startup is not None:
                    await asyncio.to_thread(on_startup)
                await send({"type": "lifespan.startup.complete"})
            await send({"type": "lifespan.shutdown.complete"})
            return
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"embedded"})

    return app


@contextlib.contextmanager
def _running(server: reflex_testing._EmbeddedServer) -> Iterator[threading.Thread]:
    """Run the server in a thread, stopping it on exit.

    Args:
        server: the embedded server.

    Yields:
        The thread serving the app.
    """
    thread = threading.Thread(target=server.run)
    thread.start()
    try:
        yield thread
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        assert not thread.is_alive()


def _assert_port_taken(host: str, port: int):
    """Assert that no socket can bind the port, even one asking to share it.

    Args:
        host: the address of the port.
        port: the port number.
    """
    with socket.socket() as thief:
        thief.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if reuse_port := getattr(socket, "SO_REUSEPORT", None):
            thief.setsockopt(socket.SOL_SOCKET, reuse_port, 1)
        with pytest.raises(OSError):
            thief.bind((host, port))
            thief.listen()


def _assert_port_free(host: str, port: int):
    """Assert that the port can be bound again.

    Args:
        host: the address of the port.
        port: the port number.
    """
    with socket.socket() as rebind:
        rebind.bind((host, port))


def _harness_with_backend(
    tmp_path, server: reflex_testing._EmbeddedServer
) -> AppHarness:
    """An AppHarness whose backend is the given server.

    Args:
        tmp_path: the app root.
        server: the backend server.

    Returns:
        The harness.
    """
    harness = AppHarness.create(root=tmp_path, app_name="embedded_app")
    harness.backend = server
    return harness


def test_embedded_server_owns_its_port():
    """The server holds its port from construction on, so no other socket can share it."""
    server = reflex_testing._EmbeddedServer(_asgi_app())
    _assert_port_taken(server.host, server.port)
    with _running(server):
        server.wait_started(timeout=15)
        _assert_port_taken(server.host, server.port)
        assert httpx.get(f"http://{server.host}:{server.port}/").content == b"embedded"


def test_poll_for_servers_waits_for_the_backend_itself(tmp_path):
    """Readiness follows the app's startup, not a connectable port.

    Args:
        tmp_path: pytest tmp_path fixture
    """
    startup = threading.Event()
    server = reflex_testing._EmbeddedServer(_asgi_app(on_startup=startup.wait))
    harness = _harness_with_backend(tmp_path, server)
    # Another listener on the port must not pass for the backend.
    foreign = socket.socket()
    with contextlib.suppress(OSError):
        foreign.bind((server.host, server.port))
        foreign.listen()
    with foreign, _running(server):
        try:
            with pytest.raises(TimeoutError):
                harness._poll_for_servers(timeout=0.5)
        finally:
            startup.set()
        assert harness._poll_for_servers(timeout=15).getsockname() == (
            server.host,
            server.port,
        )
        assert httpx.get(f"http://{server.host}:{server.port}/").content == b"embedded"


def test_embedded_server_refuses_a_taken_requested_port():
    """A requested port that is in use fails loudly instead of moving."""
    with socket.socket() as blocker:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen()
        port = blocker.getsockname()[1]
        with pytest.raises(OSError):
            reflex_testing._EmbeddedServer(_asgi_app(), port=port)
    server = reflex_testing._EmbeddedServer(_asgi_app(), port=port)
    assert server.getsockname() == ("127.0.0.1", port)
    server.should_exit = True
    server.run()


def test_failed_backend_startup_logs_and_fails_fast(tmp_path, capsys):
    """A failing lifespan startup is logged and fails readiness without the timeout.

    Args:
        tmp_path: pytest tmp_path fixture
        capsys: pytest capsys fixture
    """

    @contextlib.asynccontextmanager
    async def lifespan(app):
        msg = "lifespan boom"
        raise RuntimeError(msg)
        yield

    server = reflex_testing._EmbeddedServer(Starlette(lifespan=lifespan))
    harness = _harness_with_backend(tmp_path, server)
    with _running(server):
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="stopped without serving"):
            harness._poll_for_servers(timeout=10)
        assert time.monotonic() - started < 5
    out = capsys.readouterr().out
    assert "ASGI lifespan startup failed" in out
    assert "RuntimeError: lifespan boom" in out
    # The socket is released although no worker ever served it.
    _assert_port_free(server.host, server.port)


def test_embedded_server_stop_releases_port():
    """Stopping a serving server runs its shutdown hook and frees the port."""
    shutdown = mock.AsyncMock()
    server = reflex_testing._EmbeddedServer(_asgi_app())
    server.shutdown = shutdown
    with _running(server):
        server.wait_started(timeout=15)
    shutdown.assert_awaited_once()
    _assert_port_free(server.host, server.port)


def test_embedded_server_stopped_before_run_never_serves():
    """A server stopped before it runs returns at once and releases its port."""
    shutdown = mock.AsyncMock()
    server = reflex_testing._EmbeddedServer(_asgi_app())
    server.shutdown = shutdown
    server.should_exit = True
    server.run()
    shutdown.assert_awaited_once()
    with pytest.raises(RuntimeError, match="stopped without serving"):
        server.wait_started(timeout=0)
    _assert_port_free(server.host, server.port)


def test_embedded_server_started_is_deprecated(monkeypatch):
    """The uvicorn-style `started` flag still works, with a deprecation warning.

    Args:
        monkeypatch: pytest monkeypatch fixture
    """
    deprecate = mock.Mock()
    monkeypatch.setattr(reflex_testing.console, "deprecate", deprecate)
    server = reflex_testing._EmbeddedServer(_asgi_app())
    assert server.started is False
    with _running(server):
        server.wait_started(timeout=15)
        assert server.started is True
    assert deprecate.call_args.kwargs["feature_name"] == "AppHarness.backend.started"


def test_app_harness_frontend_env_has_development_condition(
    tmp_path, monkeypatch: pytest.MonkeyPatch, harness_mocks
) -> None:
    """The frontend dev server env enables the `development` export condition."""
    harness = AppHarness(
        app_name="testapp",
        app_source=None,
        app_path=tmp_path,
        app_module_path=tmp_path / "testapp.py",
    )
    monkeypatch.setattr(
        reflex_testing.js_runtimes,
        "get_js_package_executor",
        lambda raise_on_none: [["bun"]],
    )
    fake_socket = mock.Mock(getsockname=lambda: ("127.0.0.1", 8000))
    monkeypatch.setattr(
        AppHarness, "_poll_for_servers", lambda self, timeout: fake_socket
    )
    monkeypatch.setattr(
        reflex_testing.reflex.utils.build, "setup_frontend", lambda path: None
    )
    captured: dict = {}

    def fake_new_process(args, **kwargs):
        captured.update(kwargs)
        return mock.Mock()

    monkeypatch.setattr(
        reflex_testing.reflex.utils.processes, "new_process", fake_new_process
    )
    harness._start_frontend()
    assert "--conditions=development" in captured["env"]["NODE_OPTIONS"]


def test_app_harness_reload_forgets_states_of_every_app_module(tmp_path, monkeypatch):
    """Reloading drops the states of every module of the app's package.

    A state defined outside the app module, with an always dirty var (as
    ``rx.dynamic`` adds), must not reach the deltas of the next harness app.

    Args:
        tmp_path: pytest tmp_path fixture
        monkeypatch: pytest monkeypatch fixture
    """
    import reflex as rx

    monkeypatch.setitem(sys.modules, "harnessapp", ModuleType("harnessapp"))
    monkeypatch.setitem(
        sys.modules, "harnessapp.states", ModuleType("harnessapp.states")
    )
    widget_state = type(
        "HarnessWidgetState",
        (rx.State,),
        {"__module__": "harnessapp.states"},
    )
    widget_state._evaluate(lambda state: rx.text("widget"))
    name = widget_state.get_name()
    assert name in rx.State._always_dirty_substates

    AppHarness.create(root=tmp_path, app_name="harnessapp")._reload_state_module()

    assert name not in rx.State._always_dirty_substates
    assert widget_state not in rx.State.get_substates()


def _harness_state(module: str) -> type:
    """Define a state class whose ``__module__`` is the given module.

    Args:
        module: The module name.

    Returns:
        The state class.
    """
    import reflex as rx

    return type("HarnessPackageState", (rx.State,), {"__module__": module})


def test_app_harness_reload_forgets_states_of_the_package_module(tmp_path, monkeypatch):
    """Reloading drops the states of the app package's own ``__init__``.

    Args:
        tmp_path: pytest tmp_path fixture
        monkeypatch: pytest monkeypatch fixture
    """
    import reflex as rx

    monkeypatch.setitem(sys.modules, "harnesspkg", ModuleType("harnesspkg"))
    state = _harness_state("harnesspkg")

    AppHarness.create(root=tmp_path, app_name="harnesspkg")._reload_state_module()

    assert state not in rx.State.get_substates()


def test_app_harness_reload_forgets_states_of_a_custom_app_module_package(
    tmp_path, monkeypatch
):
    """Reloading follows the package of the imported app module, not the app name.

    Args:
        tmp_path: pytest tmp_path fixture
        monkeypatch: pytest monkeypatch fixture
    """
    import reflex as rx

    monkeypatch.setitem(sys.modules, "customapp", ModuleType("customapp"))
    monkeypatch.setitem(sys.modules, "customapp.main", ModuleType("customapp.main"))
    monkeypatch.setitem(sys.modules, "customapp.states", ModuleType("customapp.states"))
    state = _harness_state("customapp.states")
    harness = AppHarness.create(root=tmp_path, app_name="harnessapp")
    harness.app_module = sys.modules["customapp.main"]

    harness._reload_state_module()

    assert state not in rx.State.get_substates()
