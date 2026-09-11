"""Tests for the docs sidebar structure and prev/next chain."""

import pytest


@pytest.mark.parametrize("label", ["APIs", "URLs"])
def test_ai_integration_group_and_page_use_matching_acronyms(label):
    """Keep plural acronyms consistent between sidebar groups and their pages."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.ai import (
        get_ai_builder_integrations,
    )

    group = next(item for item in get_ai_builder_integrations() if item.names == label)
    assert [child.names for child in group.children] == [label]


def test_backend_authentication_links_to_enterprise_auth():
    """The backend Authentication entry is a cross-reference to the enterprise auth docs."""
    from reflex_docs.templates.docpage.sidebar.sidebar_items.learn import backend

    auth = next(item for item in backend if item.names == "Authentication")
    assert [child.link for child in auth.children] == ["/enterprise/auth/overview/"]
    assert all(child.exclude_from_prev_next for child in auth.children)


def test_cross_reference_excluded_from_prev_next_chain():
    """The enterprise auth overview keeps its enterprise-section footer links."""
    from reflex_docs.templates.docpage.sidebar.sidebar import flat_items, get_prev_next

    links = [item.link for item in flat_items]
    assert links.count("/enterprise/auth/overview/") == 1

    prev, next_ = get_prev_next("/enterprise/auth/overview/")
    assert prev is not None and prev.link == "/enterprise/event-handler-api/"
    assert next_ is not None and next_.link == "/enterprise/auth/secure-by-default/"
