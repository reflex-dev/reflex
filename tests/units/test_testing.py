"""Unit tests for the included testing tools."""

import sys
from types import ModuleType, SimpleNamespace
from unittest import mock

import pytest
import reflex_base.config
from reflex_base.constants import IS_WINDOWS
from reflex_base.registry import RegistrationContext

import reflex.reflex as reflex_cli
import reflex.testing as reflex_testing
import reflex.utils.prerequisites
from reflex.testing import AppHarness


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

    Entries registered in a prior context do not leak into the new harness's
    registrations.

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

    outer.custom_components["FooComponent"] = mock.sentinel.component
    outer.memo_definitions["format_value"] = mock.sentinel.memo

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
        assert "FooComponent" not in new_ctx.custom_components
        assert "format_value" not in new_ctx.memo_definitions
        harness_mocks.get_and_validate_app.assert_called_once_with(reload=True)
    finally:
        # `_initialize_app` attaches a new context without a matching __exit__.
        # Restore the outer context so other tests do not observe the leaked one.
        if harness._registry_token is not None:
            RegistrationContext.reset(harness._registry_token)
        # Clean up the sentinels we added to `outer`.
        outer.custom_components.pop("FooComponent", None)
        outer.memo_definitions.pop("format_value", None)


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
