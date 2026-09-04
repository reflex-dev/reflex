"""Tests for shared documentation navigation."""

from pathlib import Path

from reflex_site_shared.docs import DocsPage, build_navigation, get_prev_next


def _page(route: str, title: str, relative_path: str) -> DocsPage:
    """Create a minimal page for navigation tests.

    Returns:
        The test page.
    """
    return DocsPage(
        source_path=Path(relative_path),
        relative_path=Path(relative_path),
        route=route,
        title=title,
        description=None,
        metadata={},
        content="",
    )


def test_build_navigation_groups_pages_by_directory():
    """Build deterministic nested navigation from page paths."""
    pages = (
        _page("/reference/", "Home", "index.md"),
        _page("/reference/guide/", "Guide", "guide/index.md"),
        _page("/reference/guide/install/", "Install", "guide/install.md"),
    )

    navigation = build_navigation(pages)

    assert [(item.title, item.route) for item in navigation] == [
        ("Home", "/reference/"),
        ("Guide", "/reference/guide/"),
    ]
    assert [(item.title, item.route) for item in navigation[1].children] == [
        ("Install", "/reference/guide/install/"),
    ]


def test_get_prev_next_uses_navigation_order():
    """Resolve adjacent pages from flattened navigation order."""
    navigation = build_navigation((
        _page("/", "Home", "index.md"),
        _page("/guide/", "Guide", "guide/index.md"),
        _page("/guide/install/", "Install", "guide/install.md"),
    ))

    previous, next_ = get_prev_next(navigation, "/guide/")

    assert previous is not None
    assert previous.route == "/"
    assert next_ is not None
    assert next_.route == "/guide/install/"
