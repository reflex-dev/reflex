from collections.abc import Generator
from typing import Any

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DocsSidebarFocusApp():
    """Render the shared active sidebar leaf for focus geometry checks."""
    import reflex as rx
    from reflex_site_shared.components.docs_shell import docs_sidebar_leaf
    from reflex_site_shared.plugins import SharedSiteStylesPlugin

    class SidebarTestStylesPlugin(SharedSiteStylesPlugin):
        def get_stylesheet_paths(self, **context: Any) -> tuple[str, ...]:
            """Avoid loading site-wide styles in this focused harness."""
            return ()

    app = rx.App()

    @app.add_page
    def index():
        return rx.box(
            docs_sidebar_leaf(
                title="Introduction",
                href="/docs/introduction/",
                active=True,
                guide_margin_class="ml-[2.5rem]",
            ),
            style={"width": "80vw", "maxWidth": "19.5rem"},
        )

    rx.config.get_config().plugins = [
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
        SidebarTestStylesPlugin(),
    ]


@pytest.fixture
def docs_sidebar_focus_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the sidebar fixture app.

    Args:
        tmp_path_factory: Pytest's temporary directory factory.

    Yields:
        A running Reflex app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("docs_sidebar_focus"),
        app_source=DocsSidebarFocusApp,
    ) as harness:
        yield harness


def test_docs_sidebar_focus_outline_matches_active_pill(
    docs_sidebar_focus_app: AppHarness, page: Page
) -> None:
    """Keep the focused active link and its highlight the same size."""
    page.goto(docs_sidebar_focus_app.frontend_url)
    link = page.get_by_role("link", name="Introduction", exact=True)
    pill = link.locator("div.bg-accent")
    expect(link).to_be_visible()
    expect(pill).to_be_visible()
    link.focus()
    expect(link).to_have_css("outline-style", "solid")

    for width in (320, 390, 1440):
        page.set_viewport_size({"width": width, "height": 800})
        link_box = link.bounding_box()
        pill_box = pill.bounding_box()
        assert link_box is not None
        assert pill_box is not None
        assert abs(link_box["x"] - pill_box["x"]) < 1
        assert abs(link_box["width"] - pill_box["width"]) < 1
