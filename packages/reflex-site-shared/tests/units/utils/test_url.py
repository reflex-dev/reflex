"""Unit tests for reflex_site_shared.utils.url."""

from types import SimpleNamespace

import pytest
from reflex_site_shared.utils.url import public_url


@pytest.fixture
def patch_config(monkeypatch):
    """Patch the config read by public_url with the given values.

    Returns:
        A function taking (deploy_url, frontend_path) that installs the patch.
    """

    def _patch(deploy_url: str | None, frontend_path: str | None):
        config = SimpleNamespace(deploy_url=deploy_url, frontend_path=frontend_path)
        monkeypatch.setattr("reflex_site_shared.utils.url.get_config", lambda: config)

    return _patch


def test_public_url_joins_deploy_url_and_frontend_path(patch_config):
    patch_config("https://reflex.dev", "/docs")
    assert public_url("/llms.txt") == "https://reflex.dev/docs/llms.txt"


def test_public_url_strips_all_trailing_slashes_from_deploy_url(patch_config):
    patch_config("https://reflex.dev//", "/docs")
    assert public_url("/llms.txt") == "https://reflex.dev/docs/llms.txt"


def test_public_url_without_frontend_path(patch_config):
    patch_config("https://reflex.dev/", None)
    assert public_url("/llms.txt") == "https://reflex.dev/llms.txt"


def test_public_url_relative_when_unconfigured(patch_config):
    patch_config(None, None)
    assert public_url("/llms.txt") == "/llms.txt"


def test_public_url_fallback_base_outside_prod(monkeypatch):
    monkeypatch.setattr("reflex_site_shared.utils.url.is_prod_mode", lambda: False)
    assert (
        public_url("/state/", fallback_base="https://reflex.dev/docs/")
        == "https://reflex.dev/docs/state/"
    )
