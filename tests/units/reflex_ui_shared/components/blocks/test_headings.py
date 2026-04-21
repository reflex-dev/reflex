"""Unit tests for reflex_ui_shared.components.blocks.headings."""

from reflex_ui_shared.components.blocks.headings import HeadingLink


def _all_rendered_prop_text(component) -> str:
    """Collect the string form of every prop across a component tree.

    Args:
        component: A Reflex component.

    Returns:
        A single string containing the concatenated props of the component and
        all of its descendants.
    """
    texts = [str(component._render().props)]
    for child in component.children:
        texts.append(_all_rendered_prop_text(child))
    return " ".join(texts)


def test_heading_link_uses_full_raw_path():
    """Heading anchor href must preserve the frontend_path prefix.

    The HeadingLink anchor's href is built from ``router.page``. Using
    ``full_path`` loses the ``frontend_path`` prefix because ``path`` is the
    registered (normalized) route; ``full_raw_path`` preserves the URL the
    client actually requested, which is what a public-facing anchor needs.
    """
    component = HeadingLink.create(text="Sample Section", heading="h2")
    rendered = _all_rendered_prop_text(component)

    assert "full_raw_path" in rendered, (
        "heading anchor href should reference router.page.full_raw_path to "
        "preserve frontend_path prefix"
    )
    # "full_path" is a substring of "full_raw_path", so strip matches of the
    # correct name before checking for the stale one.
    assert "full_path" not in rendered.replace("full_raw_path", ""), (
        "heading anchor href still references router.page.full_path; this "
        "drops the frontend_path prefix when frontend_path is set"
    )
