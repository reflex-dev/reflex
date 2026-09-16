"""Canonical destinations for docs links from authored and imported Markdown."""

import pytest
from reflex_site_shared.components.blocks.typography import doclink2


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("/docs/state/overview#example", "/docs/state/overview/#example"),
        (
            "https://reflex.dev/docs/hosting/regions?q=one#title",
            "https://reflex.dev/docs/hosting/regions/?q=one#title",
        ),
        ("/docs", "/docs/"),
        ("/docs/llms.txt", "/docs/llms.txt"),
        ("/docs/guide.md", "/docs/guide.md"),
        ("#example", "#example"),
        ("https://example.com/docs/guide", "https://example.com/docs/guide"),
        ("/blog/post", "/blog/post"),
        ("/docs/state/overview/", "/docs/state/overview/"),
    ],
)
def test_markdown_doc_links_use_canonical_paths(href, expected):
    """Only known docs page paths get a slash; assets and other sites stay intact."""
    assert str(doclink2("Guide", href=href).href) == f'"{expected}"'
