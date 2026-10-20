"""Regression coverage for complete previous/next navigation targets."""

import importlib

import pytest
import reflex as rx


def test_pager_does_not_reserve_a_third_empty_column(monkeypatch):
    """Both adjacent articles receive the available reading-column width."""
    import reflex_docs.pages  # noqa: F401

    docpage_module = importlib.import_module("reflex_docs.templates.docpage.docpage")
    # Wrapping placeholder content keeps markdown demos that earlier tests
    # already executed from defining their states a second time.
    monkeypatch.setattr(
        docpage_module, "doc_edit_hrefs", dict(docpage_module.doc_edit_hrefs)
    )
    article = docpage_module.docpage(set_path="/getting-started/basics/", t="Basics")(
        lambda: rx.el.div()
    )

    pending = [article.component()]
    while pending:
        node = pending.pop()
        if "docs-page-navigation" in str(node.class_name):
            assert len(node.children) == 2
            back, forward = node.children
            assert type(back).__name__ == type(forward).__name__ == "ReactRouterLink"
            assert "col-start-2" in str(forward.class_name)
            return
        pending.extend(node.children)
    pytest.fail("Article navigation was not rendered")


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
