"""Discovery and route generation for Markdown documentation."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from reflex_site_shared.docs.models import DocsPage, DocsSiteConfig
from reflex_site_shared.utils.md import MarkdownDocument, get_md_files

_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _normalize_prefix(prefix: str) -> str:
    """Normalize a route prefix to leading and trailing slashes.

    Args:
        prefix: Consumer-provided URL prefix.

    Returns:
        The normalized prefix.
    """
    stripped = prefix.strip("/")
    return "/" if not stripped else f"/{stripped}/"


def _slug(value: str) -> str:
    """Convert a file or directory name into a URL segment.

    Args:
        value: Name to normalize.

    Returns:
        A lowercase kebab-case URL segment.
    """
    return _NON_SLUG_RE.sub("-", value.lower()).strip("-")


def _route_for(relative_path: Path, route_prefix: str) -> str:
    """Build a public route for a relative Markdown path.

    Args:
        relative_path: Markdown path relative to the content root.
        route_prefix: Normalized route prefix.

    Returns:
        A leading- and trailing-slash route.
    """
    parts = [*relative_path.parts[:-1], relative_path.stem]
    if parts[-1].lower() == "index":
        parts.pop()
    segments = [_slug(part) for part in parts]
    path = "/".join(segment for segment in segments if segment)
    return route_prefix if not path else f"{route_prefix}{path}/"


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    """Return a non-empty string metadata field.

    Args:
        metadata: Parsed frontmatter.
        key: Metadata field name.

    Returns:
        The stripped string, or ``None`` when absent.

    Raises:
        TypeError: If the field exists but is not a string.
    """
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"Documentation frontmatter '{key}' must be a string"
        raise TypeError(msg)
    return value.strip() or None


def _title_for(document: MarkdownDocument, relative_path: Path) -> str:
    """Resolve a page title from frontmatter, heading, or filename.

    Args:
        document: Parsed Markdown document.
        relative_path: Markdown path relative to the content root.

    Returns:
        The page display title.
    """
    if title := _metadata_text(document.metadata, "title"):
        return title
    if heading := _HEADING_RE.search(document.content):
        return heading.group(1).strip()
    source_name = (
        relative_path.parent.name
        if relative_path.stem == "index"
        else relative_path.stem
    )
    return source_name.replace("_", " ").replace("-", " ").title() or "Home"


def _is_excluded(relative_path: Path, patterns: tuple[str, ...]) -> bool:
    """Return whether a relative path matches an exclusion pattern.

    Args:
        relative_path: Markdown path relative to the content root.
        patterns: Consumer-provided glob patterns.

    Returns:
        Whether the path should be skipped.
    """
    relative_name = relative_path.as_posix()
    return any(fnmatchcase(relative_name, pattern) for pattern in patterns)


def discover_docs(config: DocsSiteConfig) -> tuple[DocsPage, ...]:
    """Discover Markdown pages and derive their public metadata.

    Args:
        config: Documentation content configuration.

    Returns:
        Pages sorted in stable route order, with the prefix index first.

    Raises:
        FileNotFoundError: If the content directory does not exist.
        NotADirectoryError: If the content path is not a directory.
        ValueError: If two source files normalize to the same route.
    """
    content_dir = config.content_dir
    if not content_dir.exists():
        raise FileNotFoundError(content_dir)
    if not content_dir.is_dir():
        raise NotADirectoryError(content_dir)

    route_prefix = _normalize_prefix(config.route_prefix)
    pages: list[DocsPage] = []
    routes: dict[str, Path] = {}
    for source_path in get_md_files(content_dir):
        relative_path = source_path.relative_to(content_dir)
        if _is_excluded(relative_path, config.exclude):
            continue
        route = _route_for(relative_path, route_prefix)
        if previous_path := routes.get(route):
            msg = (
                f"Duplicate documentation route {route!r}: "
                f"{previous_path} and {source_path}"
            )
            raise ValueError(msg)
        routes[route] = source_path
        document = MarkdownDocument.from_file(source_path)
        pages.append(
            DocsPage(
                source_path=source_path,
                relative_path=relative_path,
                route=route,
                title=_title_for(document, relative_path),
                description=_metadata_text(document.metadata, "description"),
                metadata=document.metadata,
                content=document.content.strip(),
            )
        )

    route_order = {route: index for index, route in enumerate(config.navigation_order)}
    unknown_routes = route_order.keys() - routes.keys()
    if unknown_routes:
        msg = f"navigation_order contains unknown routes: {sorted(unknown_routes)!r}"
        raise ValueError(msg)
    return tuple(
        sorted(
            pages,
            key=lambda page: (
                page.route not in route_order,
                route_order.get(page.route, 0),
                page.route,
            ),
        )
    )
