"""Regression coverage for complete previous/next navigation targets."""

import pytest


@pytest.mark.parametrize("forward", [False, True])
def test_pager_title_and_direction_share_one_link(forward):
    """Make the title, direction, and padding one keyboard-accessible link."""
    import reflex_docs.pages  # noqa: F401
    from reflex_docs.templates.docpage.docpage import page_navigation_link

    link = page_navigation_link(
        "What Is Reflex Build", "/ai/overview/", forward=forward
    )

    assert str(link.to).strip('"') == "/ai/overview/"
    assert len(link.children) == 2
    assert ("Next" if forward else "Back") in str(link.children[0])
    assert "What Is Reflex Build" in str(link.children[1])
    assert all(child.tag not in {"a", "ReactRouterLink"} for child in link.children)
    assert "p-3" in str(link.class_name)
    assert "focus-visible:outline-ring" in str(link.class_name)
