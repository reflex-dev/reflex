"""Deployment settings for local and hosted documentation builds."""

import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "deploy_url,expected",
    [
        (None, "http://localhost:3000"),
        ("https://staging.example.com", "https://staging.example.com"),
    ],
)
def test_docs_deployment_origin_comes_from_environment(
    monkeypatch, deploy_url, expected
):
    """Local runs keep the framework default; deployment jobs supply their origin."""
    monkeypatch.delenv("REFLEX_DEPLOY_URL", raising=False)
    monkeypatch.delenv("REFLEX_FRONTEND_PORT", raising=False)
    if deploy_url is not None:
        monkeypatch.setenv("REFLEX_DEPLOY_URL", deploy_url)
    config = runpy.run_path(str(Path(__file__).parents[1] / "rxconfig.py"))["config"]
    assert config.deploy_url == expected
