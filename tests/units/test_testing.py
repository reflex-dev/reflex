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
    for options_var in ("NODE_OPTIONS", "BUN_OPTIONS"):
        assert "--conditions=development" in captured["env"][options_var]
