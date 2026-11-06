"""Unit tests for the included testing tools."""

import sys
from types import ModuleType, SimpleNamespace
from unittest import mock

import pytest
import reflex_base.config
from reflex_base.components.memo import MEMOS
from reflex_base.constants import IS_WINDOWS
from reflex_base.environment import environment
from reflex_base.registry import RegistrationContext

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


def test_app_harness_preserves_newly_imported_shared_module_states(
    tmp_path, monkeypatch
):
    """A shared module's top-level states remain registered for the next app.

    App-owned and dynamically-created states must not leak into the base context.

    Args:
        tmp_path: pytest temporary directory
        monkeypatch: pytest monkeypatch fixture
    """
    import reflex as rx
    from reflex.state import reload_state_module

    base = RegistrationContext()
    monkeypatch.setattr(AppHarness, "_base_registration_context", base)
    app_package = "harnessapp"
    monkeypatch.setitem(sys.modules, app_package, ModuleType(app_package))
    app_module = ModuleType(f"{app_package}.main")
    monkeypatch.setitem(sys.modules, app_module.__name__, app_module)

    active = base.fork()
    token = RegistrationContext.set(active)
    modules_before_app_load = set(sys.modules)
    shared_module_name = "shared_state_package.states"
    shared_module = ModuleType(shared_module_name)
    monkeypatch.setitem(sys.modules, shared_module_name, shared_module)
    shared_module.__dict__["rx"] = rx
    exec(
        "class SharedState(rx.State):\n"
        "    count: int = 0\n"
        "    def increment(self):\n"
        "        self.count += 1\n",
        shared_module.__dict__,
    )
    shared_state = shared_module.__dict__["SharedState"]

    app_states_module = ModuleType(f"{app_package}.states")
    monkeypatch.setitem(sys.modules, app_states_module.__name__, app_states_module)
    app_states_module.__dict__["rx"] = rx
    exec(
        "class AppState(rx.State):\n"
        "    count: int = 0\n"
        "    @rx.var(cache=False)\n"
        "    def computed(self) -> int:\n"
        "        return self.count\n",
        app_states_module.__dict__,
    )
    app_state = app_states_module.__dict__["AppState"]

    dynamic_state = type(
        "DynamicState",
        (rx.State,),
        {"__module__": shared_module_name},
    )
    harness = AppHarness(
        app_name=app_package,
        app_source=None,
        app_path=tmp_path,
        app_module_path=tmp_path / "harnessapp.py",
        app_module=app_module,
        _registry_token=token,
    )
    harness._modules_before_app_load = modules_before_app_load

    monkeypatch.setitem(sys.modules, "psutil", mock.Mock())
    try:
        harness.stop()

        assert base.base_states[shared_state.get_full_name()] is shared_state
        assert any(
            registered.handler is shared_state.event_handlers["increment"]
            for registered in base.event_handlers.values()
        )
        assert app_state.get_full_name() not in base.base_states
        assert dynamic_state.get_full_name() not in base.base_states
    finally:
        # The external module remains in the base registry only for this test.
        active_token = RegistrationContext.set(active)
        reload_state_module(shared_module_name)
        reload_state_module(app_states_module.__name__)
        RegistrationContext.reset(active_token)


def test_app_harness_restarts_multi_module_app_without_reimporting_states(
    tmp_path, harness_mocks, monkeypatch
):
    """Restarting an app restores cached state submodules without re-importing them."""
    import reflex as rx
    from reflex.state import all_base_state_classes

    app_package = "restartable_harness_app"
    harness_mocks.config.module = f"{app_package}.main"
    base = RegistrationContext()
    monkeypatch.setattr(AppHarness, "_base_registration_context", base)
    monkeypatch.setattr(AppHarness, "_cached_app_state_modules", {})
    monkeypatch.setattr(reflex_cli, "_init", lambda **kwargs: None)

    package_module = ModuleType(app_package)
    package_module.__path__ = []
    app_module = ModuleType(f"{app_package}.main")
    state_module = ModuleType(f"{app_package}.states")
    state_module.__dict__["rx"] = rx
    monkeypatch.setitem(sys.modules, app_package, package_module)
    monkeypatch.setitem(sys.modules, app_module.__name__, app_module)
    monkeypatch.setitem(sys.modules, state_module.__name__, state_module)

    app_info = reflex.utils.prerequisites.AppInfo(
        app=mock.Mock(_state_manager=None), module=app_module
    )

    def load_or_check_app(*args, **kwargs):
        if "AppState" not in state_module.__dict__:
            exec(
                "class AppState(rx.State):\n"
                "    count: int = 0\n"
                "    @rx.var(cache=False)\n"
                "    def computed(self) -> int:\n"
                "        return self.count\n"
                "    @rx.event\n"
                "    def increment(self):\n"
                "        self.count += 1\n",
                state_module.__dict__,
            )
        else:
            app_state = state_module.AppState
            context = RegistrationContext.get()
            assert context.base_states[app_state.get_full_name()] is app_state
            assert any(
                handler.handler is app_state.event_handlers["increment"]
                for handler in context.event_handlers.values()
            )
            assert all_base_state_classes[app_state.get_full_name()] is None
            assert app_state.get_name() in rx.State._always_dirty_substates
        return app_info

    harness_mocks.get_and_validate_app.side_effect = load_or_check_app
    outer_context = RegistrationContext.ensure_context()
    first = AppHarness.create(
        root=tmp_path / "restartable_app",
        app_name=app_package,
        app_source="import reflex as rx\napp = rx.App()",
    )
    first.app_module_path.parent.mkdir(parents=True, exist_ok=True)
    first._initialize_app()
    app_state = state_module.AppState
    assert RegistrationContext.get().base_states[app_state.get_full_name()] is app_state
    first.stop()

    restarted = AppHarness.create(
        root=tmp_path / "restartable_app",
        app_name=app_package,
        app_source="import reflex as rx\napp = rx.App()",
    )
    restarted.app_module_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        restarted._initialize_app()
    finally:
        if restarted._registry_token is not None:
            restarted.stop()
        assert RegistrationContext.get() is outer_context


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
