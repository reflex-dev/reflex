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
    assert f'href:"{expected}"' in str(doclink2("Guide", href=href))


@pytest.mark.parametrize(
    "style", [[{"color": "red"}, {"font_weight": "600"}], {"color": "red"}]
)
def test_doclink_accepts_reflex_style_values(style):
    """Custom styles retain their values alongside the shared link defaults."""
    from reflex_site_shared.components.blocks.typography import doclink

    link = doclink("Guide", "/docs/", style=style)
    assert str(link.style["color"]) == '"red"'


def test_doclink_accepts_reactive_style():
    """Reactive style objects reach the anchor without Python dict unpacking."""
    from reflex_site_shared.components.blocks.typography import doclink

    import reflex as rx

    style = rx.Var("customStyle", _var_type=dict[str, str]).guess_type()
    assert "customStyle" in str(doclink("Guide", "/docs/", style=style))
