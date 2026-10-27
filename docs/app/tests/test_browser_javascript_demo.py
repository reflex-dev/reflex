"""Regression coverage for the browser JavaScript page's inline-script demo."""

from pathlib import Path

from reflex_docs.docgen_pipeline import render_docgen_document

DOCS = Path(__file__).resolve().parents[2]


def test_sound_demo_audio_resolves_under_frontend_path():
    """The sound effect URL carries the /docs mount, so the file is not a 404."""
    # A test-specific virtual path keeps the demo's state class from colliding
    # with the one test_docgen_double_eval registers for the real page.
    body, _ = render_docgen_document(
        "docs/api-reference/browser_javascript_sound_test.md",
        str(DOCS / "api-reference" / "browser_javascript.md"),
    )
    rendered = str(body)
    assert "/docs/vintage-button-sound-effect.mp3" in rendered
    assert 'new Audio("/vintage-button-sound-effect.mp3")' not in rendered
