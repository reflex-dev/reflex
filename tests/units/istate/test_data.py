"""Tests for ReflexURL parsing, serialization, and Var attribute access."""

from urllib.parse import parse_qsl

import reflex as rx
from reflex.istate.data import ReflexURL

SAMPLE_URL = "https://example.com:3000/posts/123?tab=comments&sort=new#top"


def test_reflex_url_parses_components():
    url = ReflexURL(SAMPLE_URL)
    assert str(url) == SAMPLE_URL
    assert url.scheme == "https"
    assert url.netloc == "example.com:3000"
    assert url.origin == "https://example.com:3000"
    assert url.path == "/posts/123"
    assert url.query == "tab=comments&sort=new"
    assert dict(url.query_parameters) == dict(parse_qsl("tab=comments&sort=new"))
    assert url.fragment == "top"


def test_reflex_url_serializes_with_all_components():
    """ReflexURL should serialize to an object with href + parsed components
    so the frontend can read any sub-field without re-parsing.
    """
    from reflex_base.utils.serializers import serialize

    url = ReflexURL(SAMPLE_URL)
    payload = serialize(url)

    assert isinstance(payload, dict)
    assert payload["href"] == SAMPLE_URL
    assert payload["scheme"] == "https"
    assert payload["netloc"] == "example.com:3000"
    assert payload["origin"] == "https://example.com:3000"
    assert payload["path"] == "/posts/123"
    assert payload["query"] == "tab=comments&sort=new"
    assert payload["query_parameters"] == dict(parse_qsl("tab=comments&sort=new"))
    assert payload["fragment"] == "top"


def test_router_url_var_supports_component_access():
    """rx.State.router.url.<component> should produce a Var whose JS expression
    accesses the corresponding key on the serialized URL object. Regression
    test for VarAttributeError: StringVar has no attribute 'scheme'.
    """

    class _State(rx.State):
        pass

    url_var = _State.router.url

    for component in ("scheme", "netloc", "origin", "path", "query", "fragment"):
        child = getattr(url_var, component)
        child_js = str(child)
        assert f'"{component}"' in child_js, (
            f"expected child Var for {component!r} to reference key "
            f"{component!r} in JS, got {child_js!r}"
        )

    # query_parameters is a mapping; attribute access must still succeed.
    assert '"query_parameters"' in str(url_var.query_parameters)


def test_router_url_var_renders_as_href_at_top_level():
    """When used as a string (e.g. in rx.text), rx.State.router.url should
    emit JS that resolves to the full URL string by reading the 'href'
    property on the serialized object.
    """

    class _State(rx.State):
        pass

    url_js = str(_State.router.url)
    assert '"href"' in url_js, (
        f"expected top-level router.url to resolve to .href in JS, got {url_js!r}"
    )
