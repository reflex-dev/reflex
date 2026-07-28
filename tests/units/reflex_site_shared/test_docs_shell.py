"""Tests for the shared documentation shell."""

from pathlib import Path

import pytest
from reflex_site_shared.components.docs_shell import (
    _docs_external_page_footer_memo,
    docs_feedback_button_toc,
    docs_left_sidebar,
    docs_page_footer,
    docs_right_sidebar,
    docs_sidebar_category,
    docs_sidebar_group,
)
from reflex_site_shared.docs.models import DocsLayoutConfig, DocsPage, NavigationItem
from reflex_site_shared.templates.docs import docs_layout

import reflex as rx


def test_shared_feedback_preserves_the_official_form_structure() -> None:
    """Keep the official feedback form DOM and thumb-button props unchanged."""
    rendered = str(docs_feedback_button_toc())

    assert "w-full gap-4 flex flex-col" in rendered
    assert "flex flex-col gap-4 w-full" in rendered
    assert "aria-label" not in rendered


def test_docs_layout_rejects_conflicting_footer_factories() -> None:
    """Require one unambiguous footer API per documentation site."""
    with pytest.raises(ValueError, match="page_footer and footer"):
        DocsLayoutConfig(
            page_footer=lambda page: rx.text(page.title),
            footer=lambda: rx.text("Footer"),
        )


def test_bannerless_sidebars_use_static_navbar_offsets() -> None:
    """Do not consult banner state when a site has no banner."""
    left = str(docs_left_sidebar(rx.text("Navigation"), show_banner=False))
    right = str(docs_right_sidebar([(2, "Overview")], show_banner=False))

    assert "hosting_banner_state" not in left
    assert "hosting_banner_state" not in right
    assert "top-[77px] h-[calc(100vh-77px)]" in left
    assert "mt-[90px]" in right


def test_bannerless_layout_uses_navbar_only_content_offset() -> None:
    """Remove the announcement-height gap from bannerless page content."""
    page = DocsPage(
        source_path=Path("guide.md"),
        relative_path=Path("guide.md"),
        route="/guide",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Guide", route="/guide"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                footer=lambda: rx.fragment(),
            ),
        )
    )

    assert "hosting_banner_state" not in rendered
    assert "pt-[7.25rem]" in rendered
    assert "pt-[9.5rem]" not in rendered


def test_docs_layout_uses_site_owned_sidebar_renderer() -> None:
    """Let a site curate navigation without replacing the shared shell."""
    page = DocsPage(
        source_path=Path("guide.md"),
        relative_path=Path("guide.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    routes: list[str] = []

    def sidebar(route: str) -> rx.Component:
        routes.append(route)
        return rx.text("Curated navigation")

    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Generated navigation", route="/guide/"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                footer=lambda: rx.fragment(),
                sidebar=sidebar,
            ),
        )
    )

    assert routes == ["/guide/"]
    assert "Curated navigation" in rendered
    assert "Generated navigation" not in rendered


def test_shared_sidebar_rows_keep_official_structure() -> None:
    """Keep category and collapsible rows visually identical across sites."""
    category = str(
        docs_sidebar_category(
            "Learn",
            "/getting-started/",
            "graduation-cap",
            True,
        )
    )
    group = str(
        docs_sidebar_group(
            "Getting Started",
            rx.text("Installation"),
            icon="rocket",
            open_=True,
        )
    )

    assert "Navigate to Learn" in category
    assert "ml-[3rem]" in category
    assert "LucideGraduationCap" in category
    assert "group/details" in group
    assert "ArrowDown01Icon" in group
    assert "left-[3rem]" in group


def test_official_docs_footer_content_is_shared() -> None:
    """Keep the complete official footer available to package docs sites."""
    component = docs_page_footer(
        issue_href="https://github.com/example/project/issues/new",
        edit_href="https://github.com/example/project/blob/main/docs/index.md",
    )
    rendered = str(component)

    assert "https://github.com/example/project/issues/new" in str(component)
    assert "Raise an issue" in rendered
    assert "Edit this page" in rendered
    assert "Links" in rendered
    assert "Documentation" in rendered
    assert "Resources" in rendered
    assert "Social link for Github" in rendered
    assert "Pynecone, Inc." in rendered
    assert "https://reflex.dev/docs/getting-started/introduction/" not in rendered
    assert "/getting-started/introduction/" in rendered

    external_rendered = str(_docs_external_page_footer_memo._definition.component)
    assert "https://reflex.dev/docs/getting-started/introduction/" in external_rendered


def test_docs_layout_uses_page_aware_footer_renderer() -> None:
    """Pass the discovered source page to a site-specific footer renderer."""
    page = DocsPage(
        source_path=Path("guide/index.md"),
        relative_path=Path("guide/index.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    paths: list[Path] = []

    def page_footer(current_page: DocsPage) -> rx.Component:
        paths.append(current_page.relative_path)
        return rx.text("Official footer")

    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Guide", route="/guide/"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                page_footer=page_footer,
            ),
        )
    )

    assert paths == [Path("guide/index.md")]
    assert "Official footer" in rendered


def test_docs_layout_supports_a_sidebar_aware_breadcrumb() -> None:
    """Allow consumers to reuse the official mobile in-page drawer."""
    page = DocsPage(
        source_path=Path("guide/index.md"),
        relative_path=Path("guide/index.md"),
        route="/guide/",
        title="Guide",
        description=None,
        metadata={},
        content="# Guide",
    )
    received: list[tuple[Path, rx.Component]] = []

    def breadcrumb(current_page: DocsPage, sidebar: rx.Component) -> rx.Component:
        received.append((current_page.relative_path, sidebar))
        return rx.text("Mobile page drawer")

    rendered = str(
        docs_layout(
            page,
            rx.text("Content"),
            (NavigationItem(title="Guide", route="/guide/"),),
            config=DocsLayoutConfig(
                show_banner=False,
                navbar=lambda: rx.fragment(),
                breadcrumb=breadcrumb,
            ),
        )
    )

    assert received[0][0] == Path("guide/index.md")
    assert "Documentation navigation" in str(received[0][1])
    assert "Mobile page drawer" in rendered
