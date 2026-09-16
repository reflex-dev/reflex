"""Tests for ReflexURL parsing, serialization, and Var attribute access."""

from collections.abc import Mapping
from urllib.parse import parse_qsl

from reflex_base.vars.object import ObjectVar
from reflex_base.vars.sequence import StringVar

import reflex as rx
from reflex.istate.data import ReflexURL, ReflexURLCastedVar

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


def test_reflex_url_serializes_when_nested_in_router_data():
    """When a RouterData is serialized (the normal state-sync path), the
    ``url`` field must come out as a full component dict rather than being
    short-circuited to a plain JSON string by json.dumps. Because ReflexURL
    is a ``str`` subclass, json.dumps handles it natively and never invokes
    the ``default=serialize`` hook, so the enclosing serializer has to
    serialize it explicitly.
    """
    import json

    from reflex_base import constants
    from reflex_base.utils.format import json_dumps

    from reflex.istate.data import RouterData

    rd = RouterData.from_router_data({
        constants.RouteVar.HEADERS: {"origin": "https://example.com:3000"},
        constants.RouteVar.PATH: "/posts/[id]",
        constants.RouteVar.ORIGIN: "/posts/123?tab=comments&sort=new#top",
    })
    payload = json.loads(json_dumps(rd))

    assert isinstance(payload["url"], dict), (
        f"expected url to serialize to a component dict, got {payload['url']!r}"
    )
    assert payload["url"]["href"] == SAMPLE_URL
    assert payload["url"]["scheme"] == "https"
    assert payload["url"]["path"] == "/posts/123"
    assert payload["url"]["query_parameters"] == dict(
        parse_qsl("tab=comments&sort=new")
    )


def test_router_url_var_is_casted():
    """rx.State.router.url should be wrapped in a ReflexURLCastedVar so the
    URL component properties resolve correctly.
    """
    assert isinstance(rx.State.router.url, ReflexURLCastedVar)


def test_router_url_var_propagates_var_data():
    """The casted URL Var (and the child component Vars it produces) must
    carry the same VarData as the underlying state-var access, so the
    compiler still emits the state-context imports and hook needed to read
    ``router`` on the frontend.
    """
    url_var = rx.State.router.url
    original_data = url_var._original._get_all_var_data()
    assert original_data is not None
    # The state import/hook needed to resolve `router` must flow through the
    # ReflexURLCastedVar wrapper...
    assert url_var._get_all_var_data() == original_data
    # ...and through every child component Var (otherwise using
    # self.router.url.scheme in a component would silently drop the state
    # subscription).
    assert url_var.scheme._get_all_var_data() == original_data
    assert url_var.query_parameters._get_all_var_data() == original_data


def test_router_url_var_string_components():
    """Each string component of router.url should render as a bracket-key on
    the router.url object and produce a StringVar typed as str. Regression
    test for VarAttributeError: StringVar has no attribute 'scheme'.
    """
    url_var = rx.State.router.url
    base = str(url_var._original)

    for component in (
        "scheme",
        "netloc",
        "origin",
        "path",
        "query",
        "fragment",
    ):
        child = getattr(url_var, component)
        assert isinstance(child, StringVar), (
            f"{component!r} should be a StringVar, got {type(child).__name__}"
        )
        assert child._var_type is str
        assert str(child) == f'{base}?.["{component}"]'


def test_router_url_var_query_parameters_is_object():
    """query_parameters should be an ObjectVar over Mapping[str, str] so
    indexing and iteration produce correctly typed child Vars.
    """
    url_var = rx.State.router.url
    qp = url_var.query_parameters

    assert isinstance(qp, ObjectVar)
    assert qp._var_type == Mapping[str, str]
    assert str(qp) == f'{url_var._original!s}?.["query_parameters"]'


def test_router_url_var_renders_as_href_at_top_level():
    """When used as a string (e.g. in rx.text), rx.State.router.url should
    emit JS that resolves to the full URL string by reading the 'href'
    property on the serialized object.
    """
    url_var = rx.State.router.url
    assert str(url_var) == f'{url_var._original!s}?.["href"]'
