"""Models shared by Markdown-backed documentation sites."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

import reflex as rx

ComponentFactory = Callable[[], rx.Component]
DocsSidebarFactory = Callable[[str], rx.Component]
DocsNavLink = tuple[str, str]
DocsNavbarAction = DocsNavLink | ComponentFactory


class DocsPageFooterFactory(Protocol):
    """Callable rendering a footer for one discovered page."""

    def __call__(self, page: DocsPage, /) -> rx.Component:
        """Render the page footer.

        Args:
            page: Current discovered documentation page.

        Returns:
            Page-specific footer component.
        """
        ...


class DocsBreadcrumbFactory(Protocol):
    """Callable rendering page breadcrumbs with access to the sidebar."""

    def __call__(
        self,
        page: DocsPage,
        sidebar: rx.Component,
        /,
    ) -> rx.Component:
        """Render page breadcrumbs or an in-page navigation drawer.

        Args:
            page: Current discovered documentation page.
            sidebar: Complete navigation component for reuse in a drawer.

        Returns:
            Page breadcrumb component.
        """
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class DocsLayoutConfig:
    """Visual configuration for the shared documentation layout.

    Args:
        site_title: Product name shown by the default navbar.
        show_banner: Whether to show the shared announcement banner.
        nav_links: Optional top-level navbar links. The documentation tree is
            used when this is empty.
        github_url: Optional repository link shown in the navbar and footer.
        show_github_navbar: Whether to show the repository link in the navbar.
            The footer edit link remains available when this is false.
        call_to_action: Optional ``(label, href)`` or component factory for the
            navbar action.
        logo: Optional replacement for the default text wordmark.
        search: Optional replacement for the shared Inkeep search.
        navbar: Optional replacement for the default navbar.
        sidebar: Optional site-owned navigation rendered inside the shared
            sidebar column. The current page route is passed to the factory.
        breadcrumb: Optional page header renderer receiving both the current
            page and complete sidebar, suitable for a mobile navigation drawer.
        page_footer: Optional page-aware footer renderer. Prefer this when
            issue or edit links depend on the Markdown source path.
        footer: Optional footer rendered below every page.
    """

    site_title: str = "Docs"
    show_banner: bool = True
    nav_links: tuple[DocsNavLink, ...] = ()
    github_url: str | None = None
    show_github_navbar: bool = True
    call_to_action: DocsNavbarAction | None = None
    logo: ComponentFactory | None = None
    search: ComponentFactory | None = None
    navbar: ComponentFactory | None = None
    sidebar: DocsSidebarFactory | None = None
    breadcrumb: DocsBreadcrumbFactory | None = None
    page_footer: DocsPageFooterFactory | None = None
    footer: ComponentFactory | None = None

    def __post_init__(self) -> None:
        """Normalize sequence inputs."""
        if self.page_footer is not None and self.footer is not None:
            msg = "DocsLayoutConfig page_footer and footer are mutually exclusive."
            raise ValueError(msg)
        object.__setattr__(self, "nav_links", tuple(self.nav_links))


@dataclass(frozen=True, slots=True, kw_only=True)
class DocsSiteConfig:
    """Configuration for discovering a documentation content tree.

    Args:
        content_dir: Directory containing the site's Markdown files.
        route_prefix: URL prefix under which documentation routes are mounted.
        exclude: Glob patterns, relative to ``content_dir``, to ignore.
        navigation_order: Central ordered route list used by the sidebar and
            previous/next navigation. Unlisted pages follow in route order.
        sitemap_base_url: Optional absolute public URL prepended to every route
            for explicit canonical sitemap locations.
    """

    content_dir: Path
    route_prefix: str = "/"
    exclude: tuple[str, ...] = ()
    navigation_order: tuple[str, ...] = ()
    sitemap_base_url: str | None = None

    def __post_init__(self) -> None:
        """Normalize path-like and sequence inputs."""
        object.__setattr__(self, "content_dir", Path(self.content_dir))
        object.__setattr__(self, "exclude", tuple(self.exclude))
        navigation_order = tuple(self.navigation_order)
        if len(navigation_order) != len(set(navigation_order)):
            msg = "navigation_order cannot contain duplicate routes"
            raise ValueError(msg)
        object.__setattr__(self, "navigation_order", navigation_order)
        if self.sitemap_base_url is not None:
            if not self.sitemap_base_url.startswith(("http://", "https://")):
                msg = "sitemap_base_url must be an absolute HTTP(S) URL"
                raise ValueError(msg)
            object.__setattr__(
                self,
                "sitemap_base_url",
                self.sitemap_base_url.rstrip("/"),
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DocsPage:
    """A discovered Markdown documentation page.

    Args:
        source_path: Absolute or configured path to the source file.
        relative_path: Source path relative to the content directory.
        route: Normalized public URL route.
        title: Display title for the page.
        description: Optional page description from frontmatter.
        metadata: Parsed YAML frontmatter.
        content: Markdown content without YAML frontmatter.
    """

    source_path: Path
    relative_path: Path
    route: str
    title: str
    description: str | None
    metadata: Mapping[str, Any]
    content: str

    def __post_init__(self) -> None:
        """Store metadata as an immutable mapping."""
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True, kw_only=True)
class NavigationItem:
    """One page or group in documentation navigation.

    Args:
        title: Display title for the item.
        route: Page route, or ``None`` for a generated grouping item.
        children: Nested navigation items.
    """

    title: str
    route: str | None = None
    children: tuple[NavigationItem, ...] = field(default_factory=tuple)
