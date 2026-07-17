"""Tests for shared site compiler plugins."""

from pathlib import Path
from types import SimpleNamespace

from reflex_site_shared.docs import DocsSiteConfig
from reflex_site_shared.plugins import DocsMarkdownPlugin, SharedSiteStylesPlugin


def test_shared_site_styles_plugin_includes_fontsource_css_by_default():
    """Import Fontsource declarations alongside the shared global CSS."""
    plugin = SharedSiteStylesPlugin()

    assert plugin.get_stylesheet_paths() == (
        "./reflex-site-shared/custom-colors.css",
        "./reflex-site-shared/tailwind-theme.css",
        "./reflex-site-shared/fonts.css",
    )


def test_shared_site_styles_plugin_can_preserve_consumer_fonts():
    """Omit Fontsource for an existing site that owns its font assets."""
    plugin = SharedSiteStylesPlugin(include_fonts=False)

    assert plugin.get_stylesheet_paths() == (
        "./reflex-site-shared/custom-colors.css",
        "./reflex-site-shared/tailwind-theme.css",
    )


def test_shared_site_styles_plugin_emits_package_css():
    """Emit every imported local stylesheet into the generated styles tree."""
    assets = SharedSiteStylesPlugin().get_static_assets()

    assert [path for path, _content in assets] == [
        Path("styles/reflex-site-shared/custom-colors.css"),
        Path("styles/reflex-site-shared/tailwind-theme.css"),
        Path("styles/reflex-site-shared/fonts.css"),
        Path("public/components/GradientButton.tsx"),
        Path("public/icons/search.svg"),
    ]
    assert all(content.strip() for _path, content in assets)
    assert "ph-conversations-widget" in assets[1][1]
    assert "export function GradientButton" in assets[3][1]
    assert "<svg" in assets[4][1]


def test_docs_markdown_plugin_emits_route_equivalents(tmp_path: Path, monkeypatch):
    """Emit Markdown at direct and trailing-slash URL variants."""
    (tmp_path / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "guides").mkdir()
    (tmp_path / "guides" / "first_steps.md").write_text(
        "# First steps\n", encoding="utf-8"
    )
    (tmp_path / "private.md").write_text("# Private\n", encoding="utf-8")
    monkeypatch.setattr(
        "reflex_site_shared.plugins.get_config",
        lambda: SimpleNamespace(frontend_path="/docs/product"),
    )

    assets = DocsMarkdownPlugin(
        docs=DocsSiteConfig(content_dir=tmp_path, exclude=("private.md",))
    ).get_static_assets()

    assert assets == (
        (Path("public/docs/product/index.md"), "# Home\n"),
        (Path("public/docs/product/.md"), "# Home\n"),
        (
            Path("public/docs/product/guides/first-steps.md"),
            "# First steps\n",
        ),
        (
            Path("public/docs/product/guides/first-steps/.md"),
            "# First steps\n",
        ),
    )


def test_docs_markdown_plugin_stages_assets_for_production_relocation(
    tmp_path: Path, monkeypatch
):
    """Preserve nested Markdown when the build moves route directories."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")
    static_dir = tmp_path / "static"
    prefixed_root = static_dir / "docs" / "product"
    (prefixed_root / "guide").mkdir(parents=True)
    (prefixed_root / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (prefixed_root / "guide" / ".md").write_text("# Guide\n", encoding="utf-8")
    (prefixed_root / "guide.html").write_text("<main>Guide</main>", encoding="utf-8")
    monkeypatch.setattr(
        "reflex_site_shared.plugins.get_config",
        lambda: SimpleNamespace(frontend_path="/docs/product"),
    )

    DocsMarkdownPlugin(docs=DocsSiteConfig(content_dir=content_dir)).post_build(
        static_dir=static_dir
    )

    assert (static_dir / "guide.md").read_text(encoding="utf-8") == "# Guide\n"
    assert (static_dir / "guide" / ".md").read_text(encoding="utf-8") == "# Guide\n"
    assert not (static_dir / "guide.html").exists()
