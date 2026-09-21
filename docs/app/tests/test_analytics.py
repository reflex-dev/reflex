"""Regression coverage for documentation page-view tracking."""


def test_docs_head_includes_google_analytics():
    """The docs app loads and configures the existing GA property exactly once."""
    from reflex_docs.reflex_docs import app

    rendered = "\n".join(str(component) for component in app.head_components)
    assert (
        rendered.count("https://www.googletagmanager.com/gtag/js?id=G-4T7C8ZD9TR") == 1
    )
    assert rendered.count("window.gtag('config', 'G-4T7C8ZD9TR')") == 1
