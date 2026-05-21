"""Validate /docs/* markdown links against the generated sitemap.xml.

For every .md file under the docs tree, parse it with reflex-docgen's
markdown parser and verify every ``[text](/docs/...)`` link:

1. The URL path contains no underscores (URLs use hyphens).
2. After stripping the ``/docs`` prefix, the path exists in sitemap.xml.

Using the real markdown AST means links inside fenced code blocks are
correctly ignored, reference-style and multi-line links are caught, and
escapes/edge cases are handled the same way the docs site renders them.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
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


def _load_sitemap_paths(sitemap_path: Path) -> set[str]:
    """Return the set of normalized URL paths declared in sitemap.xml."""
    tree = ET.parse(sitemap_path)
    paths: set[str] = set()
    for loc in tree.getroot().findall("sm:url/sm:loc", SITEMAP_NS):
        if loc.text is None:
            continue
        path = urlparse(loc.text.strip()).path
        paths.add(_strip_docs_prefix(_normalize(path)))
    return paths


def _iter_md_files(md_root: Path) -> Iterator[Path]:
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

    valid_paths = _load_sitemap_paths(sitemap_path)
    print(f"Loaded {len(valid_paths)} URLs from sitemap {sitemap_path}")

    md_files = list(_iter_md_files(md_root))
    if not md_files:
        return [f"No .md files found under {md_root}."]
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


_DOCS_APP = Path(__file__).resolve().parent.parent  # docs/app/
_MD_ROOT = _DOCS_APP.parent  # docs/
_SITEMAP = _DOCS_APP / ".web" / "public" / "sitemap.xml"


@pytest.mark.xfail(
    not _SITEMAP.is_file(),
    reason=(
        "Sitemap not generated; build the docs first "
        "(e.g. `uv run reflex export --frontend-only --no-zip`). "
        "CI passes `--runxfail` so the missing sitemap surfaces as a "
        "real failure instead of a silent xfail."
    ),
    run=False,
)
def test_docs_links_against_exported_sitemap():
    """End-to-end check: every /docs link in real markdown resolves in the sitemap."""
    errors = check(_MD_ROOT, _SITEMAP)
    assert not errors, "\n".join(errors)


SITEMAP_XML = """<?xml version='1.0' encoding='utf-8'?>
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://localhost:3000/getting-started/basics/</loc></url>
  <url><loc>http://localhost:3000/library/disclosure/</loc></url>
</urlset>
"""

SITEMAP_XML_WITH_DOCS_PREFIX = """<?xml version='1.0' encoding='utf-8'?>
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://localhost:3000/docs/getting-started/basics/</loc></url>
  <url><loc>http://localhost:3000/docs/library/disclosure/</loc></url>
</urlset>
"""


@pytest.fixture
def docs_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Create a tmp docs root + sitemap.xml and return their paths."""
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(SITEMAP_XML)
    md_root = tmp_path / "docs"
    md_root.mkdir()
    return md_root, sitemap


def test_normalize_strips_fragment_query_and_trailing_slash():
    assert _normalize("/foo/bar/") == "/foo/bar"
    assert _normalize("/foo/bar#section") == "/foo/bar"
    assert _normalize("/foo/bar?x=1") == "/foo/bar"
    assert _normalize("/") == "/"


def test_check_passes_for_valid_link(docs_tree):
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[ok](/docs/getting-started/basics)\n")
    assert check(md_root, sitemap) == []


def test_check_flags_missing_link(docs_tree):
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[bad](/docs/no-such-page)\n")
    errors = check(md_root, sitemap)
    assert len(errors) == 1
    assert "not found in sitemap" in errors[0]


def test_check_flags_underscore_and_missing(docs_tree):
    """Underscore link is reported twice: once for the underscore, once for missing."""
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[under](/docs/getting_started/basics)\n")
    errors = check(md_root, sitemap)
    assert len(errors) == 2
    assert any("underscore" in e for e in errors)
    assert any("not found in sitemap" in e for e in errors)


def test_check_ignores_fragment_for_sitemap_lookup(docs_tree):
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[anchor](/docs/getting-started/basics#section)\n")
    assert check(md_root, sitemap) == []


def test_check_allows_underscores_in_fragment(docs_tree):
    """Heading anchors like `#python_code` legitimately contain underscores."""
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[x](/docs/getting-started/basics#python_code)\n")
    assert check(md_root, sitemap) == []


def test_check_ignores_query_for_sitemap_lookup(docs_tree):
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[q](/docs/library/disclosure?x=1)\n")
    assert check(md_root, sitemap) == []


def test_check_ignores_docs_prefix_lookalikes(docs_tree):
    """`/docsfoo` should not even be treated as a /docs link."""
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[x](/docsfoo/bar)\n")
    assert check(md_root, sitemap) == []


def test_check_skips_build_dirs(docs_tree):
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text("[ok](/docs/getting-started/basics)\n")
    skipped = md_root / "node_modules" / "vendor"
    skipped.mkdir(parents=True)
    (skipped / "README.md").write_text("[bad](/docs/no-such-page)\n")
    assert check(md_root, sitemap) == []


def test_check_returns_helpful_message_when_sitemap_missing(tmp_path):
    errors = check(tmp_path, tmp_path / "missing.xml")
    assert len(errors) == 1
    assert "sitemap.xml not found" in errors[0]


def test_check_errors_when_md_root_has_no_markdown(docs_tree):
    """If the docs tree is empty, fail loudly instead of silently passing."""
    md_root, sitemap = docs_tree
    errors = check(md_root, sitemap)
    assert len(errors) == 1
    assert "No .md files found" in errors[0]


def test_check_ignores_links_in_fenced_code_blocks(docs_tree):
    """Links inside ``` fences are not real links and must be skipped."""
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text(
        "Some text.\n\n```python\n# See [doc](/docs/no-such-page) for details\n```\n"
    )
    assert check(md_root, sitemap) == []


def test_check_resolves_reference_style_links(docs_tree):
    """`[label][ref]` + `[ref]: /docs/foo` should resolve and be checked."""
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text(
        "See [the basics][b] for details.\n\n[b]: /docs/no-such-page\n"
    )
    errors = check(md_root, sitemap)
    assert len(errors) == 1
    assert "no-such-page" in errors[0]


def test_check_reports_distinct_lines_for_repeated_target(docs_tree):
    """Two links to the same /docs target on different lines must report distinct line numbers."""
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text(
        "First [x](/docs/no-such-page) here.\n"
        "Some other text.\n"
        "Second [y](/docs/no-such-page) here.\n"
    )
    errors = check(md_root, sitemap)
    assert len(errors) == 2
    line_numbers = {err.split(":", 2)[1] for err in errors}
    assert line_numbers == {"1", "3"}


def test_check_finds_links_inside_lists_and_tables(docs_tree):
    """Links inside list items and table cells must still be checked."""
    md_root, sitemap = docs_tree
    (md_root / "page.md").write_text(
        "- bullet [bad](/docs/no-such-list-page)\n\n"
        "| col |\n|-----|\n| [bad](/docs/no-such-table-page) |\n"
    )
    errors = check(md_root, sitemap)
    assert len(errors) == 2
    joined = "\n".join(errors)
    assert "no-such-list-page" in joined
    assert "no-such-table-page" in joined


def test_check_works_when_sitemap_has_docs_prefix(tmp_path: Path):
    """Both deployment styles (with or without /docs prefix in sitemap) work."""
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(SITEMAP_XML_WITH_DOCS_PREFIX)
    md_root = tmp_path / "docs"
    md_root.mkdir()
    (md_root / "page.md").write_text(
        "[ok](/docs/getting-started/basics)\n[bad](/docs/no-such-page)\n"
    )
    errors = check(md_root, sitemap)
    assert len(errors) == 1
    assert "no-such-page" in errors[0]
