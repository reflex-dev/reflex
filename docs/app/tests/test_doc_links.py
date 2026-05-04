"""Unit tests for scripts/check_doc_links.py."""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))

from check_doc_links import LINK_RE, _normalize, check

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


def test_link_re_matches_basic_link():
    matches = LINK_RE.findall("see [basics](/docs/getting-started/basics) here")
    assert matches == ["/docs/getting-started/basics"]


def test_link_re_does_not_match_docs_prefix_without_separator():
    """`/docsfoo` and `/docs-foo` must not be treated as /docs links."""
    assert LINK_RE.findall("[x](/docsfoo/bar)") == []
    assert LINK_RE.findall("[x](/docs-foo/bar)") == []


def test_link_re_keeps_fragment_and_query():
    assert LINK_RE.findall("[x](/docs/foo#anchor)") == ["/docs/foo#anchor"]
    assert LINK_RE.findall("[x](/docs/foo?q=1)") == ["/docs/foo?q=1"]


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
    skipped = md_root / "node_modules" / "vendor"
    skipped.mkdir(parents=True)
    (skipped / "README.md").write_text("[bad](/docs/no-such-page)\n")
    assert check(md_root, sitemap) == []


def test_check_returns_helpful_message_when_sitemap_missing(tmp_path):
    errors = check(tmp_path, tmp_path / "missing.xml")
    assert len(errors) == 1
    assert "sitemap.xml not found" in errors[0]


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
