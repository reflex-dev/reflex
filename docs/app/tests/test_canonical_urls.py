"""Regression tests for public docs canonical URLs."""

import importlib

import pytest


@pytest.mark.parametrize("path", ["/library/forms/button/", "library/forms/button"])
def test_canonical_url_uses_public_origin_without_deploy_url(monkeypatch, path):
    """Local build defaults must not leak into published search metadata."""
    monkeypatch.setenv("REFLEX_DEPLOY_URL", "http://localhost:3000")
    module = importlib.import_module("reflex_docs.reflex_docs")
    assert module._canonical_url(path) == (
        "https://reflex.dev/docs/library/forms/button/"
    )
