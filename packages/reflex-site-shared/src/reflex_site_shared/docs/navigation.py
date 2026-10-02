"""Navigation generation for discovered documentation pages."""

from __future__ import annotations

from dataclasses import dataclass, field

from reflex_site_shared.docs.models import DocsPage, NavigationItem


@dataclass(slots=True)
class _NavigationNode:
    """Mutable navigation node used while assembling the public tree."""

    title: str
    route: str | None = None
    children: dict[str, _NavigationNode] = field(default_factory=dict)


def _page_segments(page: DocsPage) -> tuple[str, ...]:
    """Return content hierarchy segments for a page.

    Args:
        page: Discovered documentation page.

    Returns:
        Relative content path segments without the filename extension.
    """
    parts = [*page.relative_path.parts[:-1], page.relative_path.stem]
    if parts[-1].lower() == "index":
        parts.pop()
    return tuple(part.replace("_", "-") for part in parts)


def _segment_title(segment: str) -> str:
    """Build a display title for a generated group.

    Args:
        segment: URL path segment.

    Returns:
        Title-cased display text.
    """
    return segment.replace("-", " ").title()


def _freeze(node: _NavigationNode) -> NavigationItem:
    """Convert a mutable assembly node into a public navigation item.

    Args:
        node: Internal navigation node.

    Returns:
        Immutable navigation item.
    """
    return NavigationItem(
        title=node.title,
        route=node.route,
        children=tuple(_freeze(child) for child in node.children.values()),
    )


def build_navigation(pages: tuple[DocsPage, ...]) -> tuple[NavigationItem, ...]:
    """Build nested navigation in the supplied page order.

    Pages representing a directory route become the directory's navigation
    item. Missing directory pages are represented by non-clickable groups.

    Args:
        pages: Discovered documentation pages in desired navigation order.

    Returns:
        Immutable nested navigation items.
    """
    roots: dict[str, _NavigationNode] = {}
    for page in pages:
        segments = _page_segments(page)
        if not segments:
            roots.setdefault(page.route, _NavigationNode(page.title, page.route))
            continue

        children = roots
        node: _NavigationNode | None = None
        for segment in segments:
            node = children.setdefault(
                segment, _NavigationNode(_segment_title(segment))
            )
            children = node.children
        if node is not None:
            node.title = page.title
            node.route = page.route

    return tuple(_freeze(node) for node in roots.values())


def _flatten(items: tuple[NavigationItem, ...]) -> tuple[NavigationItem, ...]:
    """Flatten clickable navigation items in display order.

    Args:
        items: Nested navigation items.

    Returns:
        Clickable items in depth-first order.
    """
    flattened: list[NavigationItem] = []
    for item in items:
        if item.route is not None:
            flattened.append(item)
        flattened.extend(_flatten(item.children))
    return tuple(flattened)


def get_prev_next(
    navigation: tuple[NavigationItem, ...], route: str
) -> tuple[NavigationItem | None, NavigationItem | None]:
    """Return the adjacent pages for a route in navigation order.

    Args:
        navigation: Nested site navigation.
        route: Current page route.

    Returns:
        Previous and next clickable items, when present.
    """
    pages = _flatten(navigation)
    for index, item in enumerate(pages):
        if item.route == route:
            previous = pages[index - 1] if index else None
            next_ = pages[index + 1] if index + 1 < len(pages) else None
            return previous, next_
    return None, None
