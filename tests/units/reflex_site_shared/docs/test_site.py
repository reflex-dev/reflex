"""Tests for shared documentation route registration."""

from pathlib import Path

import pytest
from reflex_base.components.memo import MemoComponent
from reflex_site_shared.docs import (
    DocsLayoutConfig,
    DocsPage,
    DocsSiteConfig,
    NavigationItem,
    build_docs_routes,
    docs_sidebar_leaf,
    register_docs,
)
from reflex_site_shared.templates import docs as docs_template

import reflex as rx


def test_sidebar_leaf_is_compiled_as_a_memo_component() -> None:
    """Keep repeated documentation leaves behind one React memo definition."""
    leaf = docs_sidebar_leaf(
        title="Installation",
        href="/installation/",
        active=False,
        guide_margin_class="ml-[2.5rem]",
    )

    assert isinstance(leaf, MemoComponent)


def test_build_docs_routes_binds_each_page(tmp_path: Path):
    """Create one shared route per Markdown file without late-bound closures."""
    (tmp_path / "one.md").write_text("# One", encoding="utf-8")
    (tmp_path / "two.md").write_text("# Two", encoding="utf-8")
    rendered: list[str] = []

    def renderer(page: DocsPage) -> rx.Component:
        rendered.append(page.title)
        return rx.text(page.content)

    routes = build_docs_routes(DocsSiteConfig(content_dir=tmp_path), renderer=renderer)

    assert [(route.path, route.title) for route in routes] == [
        ("/one/", "One"),
        ("/two/", "Two"),
    ]
    routes[0].component()
    routes[1].component()
    assert rendered == ["One", "Two"]


def test_register_docs_adds_discovered_pages(tmp_path: Path):
    """Register generated routes on a Reflex-compatible application."""
    (tmp_path / "index.md").write_text(
        "---\ndescription: Product documentation.\n---\n# Product Docs",
        encoding="utf-8",
    )

    class AppRecorder:
        """Record page registrations."""

        def __init__(self) -> None:
            self.pages: list[dict[str, object]] = []

        def add_page(self, **kwargs: object) -> None:
            self.pages.append(kwargs)

    app = AppRecorder()
    routes = register_docs(
        app,  # type: ignore[arg-type]
        DocsSiteConfig(
            content_dir=tmp_path,
            sitemap_base_url="https://example.com/docs/product/",
        ),
    )

    assert len(routes) == 1
    assert app.pages[0]["route"] == "/"
    assert app.pages[0]["title"] == "Product Docs"
    assert app.pages[0]["description"] == "Product documentation."
    assert app.pages[0]["context"] == {
        "sitemap": {"loc": "https://example.com/docs/product/"}
    }


def test_docs_site_config_rejects_relative_sitemap_base_url(tmp_path: Path) -> None:
    """Require explicit sitemap locations to use an absolute public URL."""
    with pytest.raises(ValueError, match="absolute HTTP"):
        DocsSiteConfig(content_dir=tmp_path, sitemap_base_url="/docs/product")


def test_layout_config_cannot_override_a_custom_layout(tmp_path: Path):
    """Reject ambiguous default and custom layout configuration."""
    (tmp_path / "index.md").write_text("# Product Docs", encoding="utf-8")

    def layout(
        page: DocsPage,
        content: rx.Component,
        navigation: tuple[NavigationItem, ...],
    ) -> rx.Component:
        del page, navigation
        return content

    with pytest.raises(
        ValueError, match="layout_config cannot be combined with a custom layout"
    ):
        build_docs_routes(
            DocsSiteConfig(content_dir=tmp_path),
            layout=layout,
            layout_config=DocsLayoutConfig(),
        )


def test_render_markdown_page_uses_absolute_source_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Namespace executable blocks by source file across documentation sites."""
    source_path = tmp_path / "site" / "index.md"
    source_path.parent.mkdir()
    source_path.write_text("# Product Docs", encoding="utf-8")
    page = DocsPage(
        source_path=source_path,
        relative_path=Path("index.md"),
        route="/",
        title="Product Docs",
        description=None,
        metadata={},
        content="# Product Docs",
    )
    calls: list[tuple[str, str, str]] = []

    def render_markdown(
        text: str, *, virtual_filepath: str = "", filename: str = ""
    ) -> rx.Component:
        calls.append((text, virtual_filepath, filename))
        return rx.text("rendered")

    monkeypatch.setattr(docs_template, "render_markdown", render_markdown)

    docs_template.render_markdown_page(page)

    resolved = str(source_path.resolve())
    assert calls == [("# Product Docs", resolved, resolved)]


def test_default_docs_layout_contains_configured_site_shell(tmp_path: Path) -> None:
    """Render the banner, navigation, TOC, repository action, and footer."""
    source_path = tmp_path / "guide.md"
    page = DocsPage(
        source_path=source_path,
        relative_path=Path("guide.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide\n\n## Installation",
    )
    navigation = (NavigationItem(title="Guide", route="/guide/"),)

    component = docs_template.docs_layout(
        page,
        rx.text("Documentation body"),
        navigation,
        config=DocsLayoutConfig(
            site_title="Product",
            nav_links=(("Overview", "/"),),
            github_url="https://github.com/example/product",
            call_to_action=("Get Started", "/guide/"),
        ),
    )
    rendered = str(component)

    assert "PRODUCT" in rendered
    assert "On This Page" in rendered
    assert "Installation" in rendered
    assert "Get Started" in rendered
    assert "Overview" in rendered
    assert "Did you find this useful?" in rendered
    assert "https://github.com/example/product" in rendered


def test_repository_link_can_remain_in_footer_without_navbar_button(
    tmp_path: Path,
) -> None:
    """Let package docs replace the GitHub navbar action without losing Edit."""
    page = DocsPage(
        source_path=tmp_path / "guide.md",
        relative_path=Path("guide.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    rendered = str(
        docs_template.docs_layout(
            page,
            rx.text("Documentation body"),
            (NavigationItem(title="Guide", route="/guide/"),),
            config=DocsLayoutConfig(
                site_title="Product",
                github_url="https://github.com/example/product",
                show_github_navbar=False,
            ),
        )
    )

    assert "View Product on GitHub" not in rendered
    assert "https://github.com/example/product" in rendered
