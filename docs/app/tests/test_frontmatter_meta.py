"""Unit tests for the frontmatter metadata helpers in reflex_docs.pages.docs."""

from reflex_docs.pages.docs import _frontmatter_for, get_image_from_frontmatter


def test_frontmatter_for_extracts_fields(tmp_path):
    """Frontmatter fields are parsed from a doc with a body."""
    doc = tmp_path / "page.md"
    doc.write_text(
        "---\ntitle: Page\nimage: /previews/page.webp\n---\n\n# Page\n\nBody prose.\n",
        encoding="utf-8",
    )
    fm = _frontmatter_for(str(doc))
    assert fm is not None
    assert fm.title == "Page"
    assert fm.image == "/previews/page.webp"


def test_frontmatter_for_none_without_frontmatter(tmp_path):
    """Docs without a frontmatter block yield None."""
    doc = tmp_path / "plain.md"
    doc.write_text("# Plain\n\nNo frontmatter here.\n", encoding="utf-8")
    assert _frontmatter_for(str(doc)) is None


def test_frontmatter_for_unreadable_file_returns_none(tmp_path):
    """A failed read yields None instead of aborting route registration."""
    assert _frontmatter_for(str(tmp_path / "missing.md")) is None


def test_get_image_from_frontmatter(tmp_path):
    """The image helper returns the frontmatter image or None."""
    with_image = tmp_path / "with_image.md"
    with_image.write_text(
        "---\nimage: /previews/foo.webp\n---\n\n# T\n", encoding="utf-8"
    )
    without_image = tmp_path / "without_image.md"
    without_image.write_text("---\ntitle: T\n---\n\n# T\n", encoding="utf-8")
    assert get_image_from_frontmatter(str(with_image)) == "/previews/foo.webp"
    assert get_image_from_frontmatter(str(without_image)) is None
