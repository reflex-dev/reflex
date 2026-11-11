"""Shared metadata asset regressions."""

from reflex_base.config import get_config
from reflex_site_shared.meta.meta import favicons_links

import reflex as rx


def test_svg_favicon_preserves_mount_and_content_version(tmp_path, monkeypatch):
    """Consumer favicon URLs retain the mount prefix and update after edits."""
    asset = rx.asset
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(get_config(), "frontend_path", "/docs")
    (tmp_path / "assets").mkdir()
    favicon = tmp_path / "assets/favicon.svg"
    favicon.write_text("<svg>first</svg>")
    monkeypatch.setattr(
        rx, "asset", lambda path: asset(path) if path == "favicon.svg" else f"/{path}"
    )
    first = str(favicons_links()[-2])
    assert 'href:"/docs/favicon.svg?v=' in first
    favicon.write_text("<svg>second</svg>")
    second = str(favicons_links()[-2])
    assert 'href:"/docs/favicon.svg?v=' in second
    assert first != second
