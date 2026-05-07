"""Unit tests for the included testing tools."""

import sys
from types import ModuleType, SimpleNamespace
from unittest import mock

import pytest
import reflex_base.config
from reflex_base.components.component import CUSTOM_COMPONENTS
from reflex_base.constants import IS_WINDOWS

import reflex.reflex as reflex_cli
import reflex.testing as reflex_testing
import reflex.utils.prerequisites
from reflex.experimental.memo import EXPERIMENTAL_MEMOS
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

    monkeypatch.setattr(reflex_testing, "get_config", lambda reload=False: fake_config)
    monkeypatch.setattr(
        reflex_base.config, "get_config", lambda reload=False: fake_config
    )
    monkeypatch.setattr(
        reflex.utils.prerequisites,
        "get_and_validate_app",
        get_and_validate_app,
    )

    return SimpleNamespace(
        config=fake_config,
        get_and_validate_app=get_and_validate_app,
    )


def test_app_harness_initialize_clears_memo_registries(
    tmp_path, preserve_memo_registries, harness_mocks, monkeypatch
):
    """Ensure app initialization clears leaked memo registries.

    Args:
        tmp_path: pytest tmp_path fixture
        preserve_memo_registries: restores global memo registries after the test
        harness_mocks: shared AppHarness mock setup
        monkeypatch: pytest monkeypatch fixture
    """
    monkeypatch.setattr(reflex_cli, "_init", lambda **kwargs: None)

    CUSTOM_COMPONENTS["FooComponent"] = mock.sentinel.component
    EXPERIMENTAL_MEMOS["format_value"] = mock.sentinel.memo

    harness = AppHarness.create(
        root=tmp_path / "memo_app",
        app_source="import reflex as rx\napp = rx.App()",
        app_name="memo_app",
    )
    harness.app_module_path.parent.mkdir(parents=True, exist_ok=True)
    harness._initialize_app()

    assert "FooComponent" not in CUSTOM_COMPONENTS
    assert "format_value" not in EXPERIMENTAL_MEMOS
    harness_mocks.get_and_validate_app.assert_called_once_with(reload=True)


def test_app_harness_initialize_reloads_existing_imported_app(
    tmp_path, preserve_memo_registries, harness_mocks, monkeypatch
):
    """Ensure pre-existing imported apps are reloaded after memo registry reset.

    Args:
        tmp_path: pytest tmp_path fixture
        preserve_memo_registries: restores global memo registries after the test
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
