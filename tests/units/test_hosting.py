"""Tests for the hosting CLI interface in ``reflex.hosting``."""

import pytest
from pytest_mock import MockerFixture
from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import environment

from reflex import hosting


@pytest.fixture
def deploy_env(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture):
    """Isolate deploy env vars and stub the app-dir prerequisites.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        mocker: The pytest-mock fixture.
    """
    monkeypatch.setenv(environment.REFLEX_SSR.name, "")
    monkeypatch.setenv(environment.REFLEX_COMPILE_CONTEXT.name, "")
    mocker.patch.object(hosting.prerequisites, "assert_in_reflex_dir")
    mocker.patch.object(hosting.prerequisites, "needs_reinit", return_value=False)
    mocker.patch.object(hosting.prerequisites, "check_latest_package_version")


def test_prepare_deploy_sets_deploy_context(deploy_env):
    """prepare_deploy sets the DEPLOY compile context and returns config values."""
    prep = hosting.prepare_deploy(ssr=False)

    assert environment.REFLEX_COMPILE_CONTEXT.get() == constants.CompileContext.DEPLOY
    assert prep.ssr is False
    assert environment.REFLEX_SSR.get() is False
    config = get_config()
    assert prep.app_name == config.app_name
    assert prep.loglevel == config.loglevel


def test_prepare_deploy_env_var_overrides_flag(
    deploy_env, monkeypatch: pytest.MonkeyPatch
):
    """An already-set REFLEX_SSR env var wins over the flag value."""
    monkeypatch.setenv(environment.REFLEX_SSR.name, "False")

    prep = hosting.prepare_deploy(ssr=True)

    assert prep.ssr is False


def test_prepare_deploy_reinits_when_needed(deploy_env, mocker: MockerFixture):
    """prepare_deploy initializes the app when the app dir needs reinit."""
    mocker.patch.object(hosting.prerequisites, "needs_reinit", return_value=True)
    init = mocker.patch("reflex.reflex._init")

    hosting.prepare_deploy()

    init.assert_called_once_with(name=get_config().app_name)


def test_export_for_deploy_fills_loglevel(mocker: MockerFixture):
    """export_for_deploy forwards its arguments and supplies the loglevel."""
    export = mocker.patch.object(hosting, "export")

    hosting.export_for_deploy(
        zip_dest_dir="/tmp/deploy",
        api_url="https://api.example.com",
        deploy_url="https://app.example.com",
        frontend=True,
        backend=False,
        upload_db_file=False,
        zipping=True,
    )

    export.assert_called_once_with(
        zip_dest_dir="/tmp/deploy",
        api_url="https://api.example.com",
        deploy_url="https://app.example.com",
        frontend=True,
        backend=False,
        zipping=True,
        loglevel=get_config().loglevel.subprocess_level(),
        upload_db_file=False,
        backend_excluded_dirs=(),
        prerender_routes=True,
    )
