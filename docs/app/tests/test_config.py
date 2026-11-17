"""Deployment settings for local and hosted documentation builds."""

import runpy
import subprocess
import sys
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
    """Builds preserve the chart's expected origin unless explicitly overridden."""
    monkeypatch.delenv("REFLEX_DEPLOY_URL", raising=False)
    monkeypatch.delenv("REFLEX_FRONTEND_PORT", raising=False)
    if deploy_url is not None:
        monkeypatch.setenv("REFLEX_DEPLOY_URL", deploy_url)
    config = runpy.run_path(str(Path(__file__).parents[1] / "rxconfig.py"))["config"]
    assert config.frontend_url == expected


def test_docs_head_identifies_cross_origin_video_embeds(monkeypatch):
    """YouTube embeds receive an origin even under a same-origin response policy."""
    monkeypatch.setenv("CI", "true")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from reflex_docs.reflex_docs import app

policies = [
    component.render()
    for component in app.head_components
    if component.tag == "meta" and str(component.name) == '"referrer"'
]
assert len(policies) == 1, policies
assert 'content:"strict-origin-when-cross-origin"' in policies[0]["props"]
print("referrer policy verified")
""",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "referrer policy verified" in result.stdout, result.stdout + result.stderr
