"""Tests for reflex.utils.exec."""

from __future__ import annotations

import pytest

from reflex.utils.exec import _apply_frontend_path


@pytest.mark.parametrize(
    ("listening_url", "frontend_path", "expected"),
    [
        # Empty frontend_path is a no-op.
        ("http://localhost:3001/", "", "http://localhost:3001/"),
        # Vite has not yet baked the path into the URL (e.g. prod listening line).
        ("http://localhost:3001/", "/app", "http://localhost:3001/app/"),
        ("http://localhost:3001/", "app", "http://localhost:3001/app/"),
        ("http://localhost:3001/", "app/", "http://localhost:3001/app/"),
        ("http://localhost:3001/", "/app/", "http://localhost:3001/app/"),
        # Vite already prints the URL with the base appended (dev server).
        # Either form of frontend_path must NOT cause the path to be duplicated.
        ("http://localhost:3001/noslash/", "noslash", "http://localhost:3001/noslash/"),
        (
            "http://localhost:3001/noslash/",
            "/noslash",
            "http://localhost:3001/noslash/",
        ),
        # Multi-segment frontend_path.
        (
            "http://localhost:3001/",
            "app/v1",
            "http://localhost:3001/app/v1/",
        ),
        (
            "http://localhost:3001/app/v1/",
            "app/v1",
            "http://localhost:3001/app/v1/",
        ),
    ],
)
def test_apply_frontend_path(listening_url: str, frontend_path: str, expected: str):
    """Issue #6360: frontend_path without a leading slash must not duplicate path segments."""
    assert _apply_frontend_path(listening_url, frontend_path) == expected
