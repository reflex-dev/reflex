"""Validate /docs/* markdown links against the generated sitemap.xml.

For every .md file under the docs tree, parse it with reflex-docgen's
markdown parser and verify every `[text](/docs/...)` link:

1. The URL path contains no underscores (URLs use hyphens).
2. After stripping the `/docs` prefix, the path exists in sitemap.xml.

Using the real markdown AST means links inside fenced code blocks are
correctly ignored, reference-style and multi-line links are caught, and
escapes/edge cases are handled the same way the docs site renders them.

The whole-docs run is driven by
``tests/test_doc_links.py::test_docs_links_against_exported_sitemap``,
which requires ``reflex export`` to have populated
``.web/public/sitemap.xml``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

from reflex_docgen.markdown import (
    Block,
    BoldSpan,
    DirectiveBlock,
    HeadingBlock,
    ImageSpan,
    ItalicSpan,
    LinkSpan,
    ListBlock,
    QuoteBlock,
    Span,
    StrikethroughSpan,
    TableBlock,
    TextBlock,
    parse_document,
)

SITEMAP_NS = {"sm": "https://www.sitemaps.org/schemas/sitemap/0.9"}
SKIP_DIRS = {".web", "node_modules", "__pycache__", ".git", ".venv", "dist", "build"}


def _normalize(path: str) -> str:
    path = path.split("#", 1)[0].split("?", 1)[0]
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def _strip_docs_prefix(path: str) -> str:
    """Drop a leading `/docs` segment so both deployment styles compare equal."""
    if path == "/docs":
        return "/"
    if path.startswith("/docs/"):
        return path[len("/docs") :]
    return path


def load_sitemap_paths(sitemap_path: Path) -> set[str]:
    """Return the set of normalized URL paths declared in sitemap.xml."""
    tree = ET.parse(sitemap_path)
    paths: set[str] = set()
    for loc in tree.getroot().findall("sm:url/sm:loc", SITEMAP_NS):
        if loc.text is None:
            continue
        path = urlparse(loc.text.strip()).path
        paths.add(_strip_docs_prefix(_normalize(path)))
    return paths


def iter_md_files(md_root: Path) -> Iterator[Path]:
    """Yield .md files under md_root, skipping build/vendor directories."""
    for path in md_root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.relative_to(md_root).parts):
            continue
        yield path


def _walk_spans(spans: tuple[Span, ...]) -> Iterator[LinkSpan]:
    """Recursively yield every LinkSpan inside a span tree."""
    for span in spans:
        if isinstance(span, LinkSpan):
            yield span
            yield from _walk_spans(span.children)
        elif isinstance(span, (BoldSpan, ItalicSpan, StrikethroughSpan, ImageSpan)):
            yield from _walk_spans(span.children)


def _walk_blocks(blocks: tuple[Block, ...]) -> Iterator[LinkSpan]:
    """Recursively yield every LinkSpan in a block tree, skipping CodeBlock."""
    for block in blocks:
        if isinstance(block, (HeadingBlock, TextBlock)):
            yield from _walk_spans(block.children)
        elif isinstance(block, ListBlock):
            for item in block.items:
                yield from _walk_blocks(item.children)
        elif isinstance(block, (QuoteBlock, DirectiveBlock)):
            yield from _walk_blocks(block.children)
        elif isinstance(block, TableBlock):
            for row in (block.header, *block.rows):
                for cell in row.cells:
                    yield from _walk_spans(cell.children)


def _line_for(text: str, target: str, cursor: int) -> tuple[int, int]:
    """Locate the next occurrence of `](target)` after cursor.

    Returns ``(line_number, new_cursor)``. If the link is reference-style
    (no `](target)` in source), falls back to scanning for `]: target`.
    Returns ``line_number == 0`` if the target can't be located.
    """
    needle = "](" + target
    pos = text.find(needle, cursor)
    if pos == -1:
        # Reference-style links resolve to the same target but live in
        # a `[label]: target` definition further down the file.
        pos = text.find("]: " + target, cursor)
    if pos == -1:
        return 0, cursor
    return text.count("\n", 0, pos) + 1, pos + len(needle)


def check(md_root: Path, sitemap_path: Path) -> list[str]:
    """Return a list of human-readable error strings.

    Prints a per-link trail and a summary so CI logs make it obvious which
    files were scanned and which links were validated.
    """
    if not sitemap_path.is_file():
        return [
            f"sitemap.xml not found at {sitemap_path}. "
            "Build the frontend first (e.g. `uv run reflex export --frontend-only --no-zip`)."
        ]

    valid_paths = load_sitemap_paths(sitemap_path)
    print(f"Loaded {len(valid_paths)} URLs from sitemap {sitemap_path}")

    md_files = list(iter_md_files(md_root))
    if not md_files:
        return [f"No .md files found under {md_root}. Check --md-root."]
    print(f"Scanning {len(md_files)} markdown file(s) under {md_root}")

    errors: list[str] = []
    links_checked = 0
    for md_file in md_files:
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            doc = parse_document(text)
        except Exception as exc:
            errors.append(f"{md_file}: failed to parse markdown ({exc})")
            continue

        cursor = 0
        for link in _walk_blocks(doc.blocks):
            target = link.target
            if not (target == "/docs" or target.startswith("/docs/")):
                continue

            line_no, cursor = _line_for(text, target, cursor)
            location = f"{md_file}:{line_no}" if line_no else str(md_file)
            links_checked += 1

            path_only = _normalize(target)
            sitemap_key = _strip_docs_prefix(path_only)
            has_underscore = "_" in path_only
            in_sitemap = sitemap_key in valid_paths
            status = "OK" if (in_sitemap and not has_underscore) else "FAIL"
            print(f"  [{status:<4}] {location} -> {target}")

            if has_underscore:
                errors.append(
                    f"{location}: link contains an underscore (use hyphens): {target!r}"
                )
            if not in_sitemap:
                errors.append(
                    f"{location}: {target!r} -> {sitemap_key!r} not found in sitemap"
                )

    print(f"Checked {links_checked} /docs link(s) across {len(md_files)} file(s).")
    return errors


