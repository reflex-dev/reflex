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


def test_url_data_serializes_like_reflex_url():
    """URLData (the per-field storage form of the router URL) must serialize
    to the same component dict shape as the eager ReflexURL serialization, so
    the frontend var access patterns are unchanged by the router var split.
    """
    import json

    from reflex_base.utils.format import json_dumps

    from reflex.istate.data import URLData, _serialize_reflex_url

    url = ReflexURL(SAMPLE_URL)
    payload = json.loads(json_dumps(URLData.from_url(url)))
    assert payload == json.loads(json_dumps(_serialize_reflex_url(url)))
    # The runtime value of href keeps parsed-component access on the backend.
    assert isinstance(URLData.from_url(url).href, ReflexURL)


def test_router_var_resolves_to_per_field_base_vars():
    """State.router is a switchboard: each attribute must resolve directly to
    the per-field base var, so a navigation delta that only carries the
    navigation-scoped vars still updates every rendered router expression.
    """
    prefix = "reflex___state____state"
    assert (
        str(rx.State.router.session.client_token)
        == f'{prefix}.router_session_rx_state_?.["client_token"]'
    )
    assert (
        str(rx.State.router.headers.user_agent)
        == f'{prefix}.router_headers_rx_state_?.["user_agent"]'
    )
    assert (
        str(rx.State.router.page.raw_path)
        == f'{prefix}.router_page_rx_state_?.["raw_path"]'
    )
    assert str(rx.State.router.url) == f'{prefix}.router_url_rx_state_?.["href"]'
    assert str(rx.State.router.url.path) == f'{prefix}.router_url_rx_state_?.["path"]'
    assert str(rx.State.router.route_id) == f"{prefix}.router_route_id_rx_state_"


def test_router_var_renders_composed_object():
    """Rendering State.router itself produces an object literal over the
    per-field vars, matching the pre-split serialized router shape.
    """
    prefix = "reflex___state____state"
    assert str(rx.State.router) == (
        "({ "
        f'"session": {prefix}.router_session_rx_state_, '
        f'"headers": {prefix}.router_headers_rx_state_, '
        f'"page": {prefix}.router_page_rx_state_, '
        f'"url": {prefix}.router_url_rx_state_, '
        f'"route_id": {prefix}.router_route_id_rx_state_'
        " })"
    )


def test_router_var_carries_state_var_data():
    """The switchboard var must merge the per-field vars' VarData so hooks
    and context wiring for the root state are set up when it renders.
    """
    var_data = rx.State.router._get_all_var_data()
    assert var_data is not None
    assert var_data.state == rx.State.get_full_name()
