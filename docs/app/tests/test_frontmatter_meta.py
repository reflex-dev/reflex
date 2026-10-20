"""Unit tests for the frontmatter metadata helpers in reflex_docs.pages.docs."""

import pytest

from reflex_docs.pages.docs import _frontmatter_for, get_image_from_frontmatter


@pytest.mark.parametrize("prefix", ["", "\ufeff", " \n\n", "\ufeff \n"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_authored_title_changes_search_title_without_changing_route(
    tmp_path, prefix, newline
):
    """A descriptive authored title must reach the page head, not its URL."""
    from reflex_docs.docgen_pipeline import get_docgen_toc, render_docgen_document
    from reflex_docs.pages.docs import get_component_docgen, resolve_doc_route

    doc = tmp_path / "example.md"
    description = "Build a dashboard with linked charts and shared Python state."
    doc.write_bytes(
        (
            prefix
            + "---\ntitle: Build Linked Charts in Python\n"
            + f"meta_description: {description}\n---\n\n# Linked charts\n"
        )
        .replace("\n", newline)
        .encode("utf-8")
    )
    route = get_component_docgen("docs/getting_started/example.md", str(doc), "example")
    assert route.title.startswith("Build Linked Charts in Python · ")
    assert route.path == "/getting-started/example/"
    assert route.description == description
    assert (
        resolve_doc_route("docs/getting_started/example.md", "example").display_title
        == "Example"
    )
    body, _ = render_docgen_document("docs/getting_started/example.md", str(doc))
    rendered = str(body)
    assert "Linked charts" in rendered
    assert "meta_description" not in rendered
    assert "Build Linked Charts in Python" not in rendered
    assert get_docgen_toc(doc) == [(1, "Linked charts")]


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


def test_library_component_title_preserves_underscores():
    """Component page titles preserve underscores in component names."""
    from reflex_docs.pages.docs.metadata import docs_metadata

    title, _ = docs_metadata("library/tables-and-data-grids/data_table/", "Data Table", None)
    assert "rx.data_table" in title, "Component name should preserve underscores"
    assert "rx.data table" not in title, "Component name should not have spaces"
    assert title == "rx.data_table: Python Data Table Component · Reflex"


def test_library_component_title_preserves_hyphens():
    """Low-level multi-component pages use breadcrumb format."""
    from reflex_docs.pages.docs.metadata import docs_metadata

    title, _ = docs_metadata("library/forms/select-ll/", "Select (Low Level)", None)
    assert "rx." not in title, "Multi-component pages should use breadcrumb format"
    assert title == "Select (Low Level) · Forms · Library · Reflex"


def test_library_single_component_ll_page_uses_component_format():
    """Single-component low-level pages use component format."""
    from reflex_docs.pages.docs.metadata import docs_metadata

    title, _ = docs_metadata("library/forms/input-ll/", "Input (Low Level)", None)
    assert "rx.input.slot" in title, "Single-component -ll pages should use component format"
    assert title == "rx.input.slot: Python Input (Low Level) Component · Reflex"


def test_library_category_title_uses_display_name():
    """Category pages use the display name, not component format."""
    from reflex_docs.pages.docs.metadata import docs_metadata

    title, _ = docs_metadata("library/tables-and-data-grids/", "Tables And Data Grids", None)
    assert "rx." not in title, "Category pages should not have rx. prefix"
    assert title == "Tables And Data Grids · Library · Reflex"


def test_library_index_title():
    """Library index page has custom title."""
    from reflex_docs.pages.docs.metadata import docs_metadata

    title, desc = docs_metadata("library/", "Component Library", None)
    assert title == "Component Library · Reflex"
    assert "Python UI Component Library" in desc or "Browse Reflex UI components" in desc or "Build web UIs in pure Python" in desc


def test_non_library_title_unchanged():
    """Non-library pages maintain breadcrumb-style titles."""
    from reflex_docs.pages.docs.metadata import docs_metadata

    title, _ = docs_metadata("state/overview/", "State Overview", None)
    assert "rx." not in title, "Non-library pages should not have rx. prefix"
    assert title == "State Overview · State · Reflex"


def test_html_collection_pages_not_component_format():
    """HTML element collection pages use breadcrumb format, not component format."""
    from reflex_docs.pages.docs.metadata import docs_metadata

    title, _ = docs_metadata("library/html/text/", "HTML Text Elements", None)
    assert "rx." not in title, "HTML collection pages should not have rx. prefix"
    assert title == "HTML Text Elements · HTML · Library · Reflex"
