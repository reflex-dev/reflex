"""Tests for the docs sidebar structure and prev/next chain."""


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
