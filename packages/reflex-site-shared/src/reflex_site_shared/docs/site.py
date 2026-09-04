"""Route creation and registration for shared documentation sites."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

import reflex as rx
from reflex_site_shared.docs.content import discover_docs
from reflex_site_shared.docs.models import DocsPage, DocsSiteConfig, NavigationItem
from reflex_site_shared.docs.navigation import build_navigation
from reflex_site_shared.route import Route

if TYPE_CHECKING:
    from reflex_site_shared.docs.models import DocsLayoutConfig

DocsPageRenderer = Callable[[DocsPage], rx.Component]
DocsPageLayout = Callable[
    [DocsPage, rx.Component, tuple[NavigationItem, ...]], rx.Component
]


def build_docs_routes(
    config: DocsSiteConfig,
    *,
    renderer: DocsPageRenderer | None = None,
    layout: DocsPageLayout | None = None,
    layout_config: DocsLayoutConfig | None = None,
) -> tuple[Route, ...]:
    """Create shared routes for every Markdown page in a content tree.

    Args:
        config: Documentation content configuration.
        renderer: Optional function that converts a discovered page into page
            content. Defaults to the shared Markdown renderer.
        layout: Optional function that wraps rendered content in the site
            shell. Defaults to the shared documentation layout.
        layout_config: Optional configuration for the default shared layout.

    Returns:
        Routes ready to register on a Reflex application.
    """
    if layout is not None and layout_config is not None:
        msg = "layout_config cannot be combined with a custom layout"
        raise ValueError(msg)

    if renderer is None or layout is None:
        from reflex_site_shared.templates.docs import docs_layout, render_markdown_page

        renderer = renderer or render_markdown_page
        layout = layout or partial(docs_layout, config=layout_config)

    pages = discover_docs(config)
    navigation = build_navigation(pages)

    def make_component(page: DocsPage) -> Callable[[], rx.Component]:
        """Bind one page to its renderer and layout.

        Args:
            page: Page to bind.

        Returns:
            Zero-argument page component factory.
        """

        def component() -> rx.Component:
            """Render the bound documentation page.

            Returns:
                The complete page component.
            """
            return layout(page, renderer(page), navigation)

        return component

    return tuple(
        Route(
            path=page.route,
            title=page.title,
            description=page.description,
            component=make_component(page),
        )
        for page in pages
    )


def register_docs(
    app: rx.App,
    config: DocsSiteConfig,
    *,
    renderer: DocsPageRenderer | None = None,
    layout: DocsPageLayout | None = None,
    layout_config: DocsLayoutConfig | None = None,
) -> tuple[Route, ...]:
    """Discover and register a Markdown documentation site on an app.

    Args:
        app: Reflex application receiving the generated pages.
        config: Documentation content configuration.
        renderer: Optional function that converts a discovered page into page
            content. Defaults to the shared Markdown renderer.
        layout: Optional function that wraps rendered content in the site
            shell. Defaults to the shared documentation layout.
        layout_config: Optional configuration for the default shared layout.

    Returns:
        The registered routes for inspection or further processing.
    """
    routes = build_docs_routes(
        config,
        renderer=renderer,
        layout=layout,
        layout_config=layout_config,
    )
    for route in routes:
        context = (
            {
                "sitemap": {
                    "loc": f"{config.sitemap_base_url}{route.path}",
                }
            }
            if config.sitemap_base_url is not None
            else None
        )
        app.add_page(
            component=route.component,
            route=route.path,
            title=route.title,
            description=route.description,
            context=context,
        )
    return routes


__all__ = ["build_docs_routes", "register_docs"]
