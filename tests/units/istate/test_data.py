"""Tests for ReflexURL parsing, serialization, and Var attribute access."""

from collections.abc import Mapping
from typing import cast
from urllib.parse import parse_qsl

import pytest
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
        == f'{prefix}.rx_router_session_rx_state_?.["client_token"]'
    )
    assert (
        str(rx.State.router.headers.user_agent)
        == f'{prefix}.rx_router_headers_rx_state_?.["user_agent"]'
    )
    assert (
        str(rx.State.router.page.raw_path)
        == f'{prefix}.rx_router_page_rx_state_?.["raw_path"]'
    )
    assert str(rx.State.router.url) == f'{prefix}.rx_router_url_rx_state_?.["href"]'
    assert (
        str(rx.State.router.url.path) == f'{prefix}.rx_router_url_rx_state_?.["path"]'
    )
    assert str(rx.State.router.route_id) == f"{prefix}.rx_router_route_id_rx_state_"


def test_router_var_renders_composed_object():
    """Rendering State.router itself produces an object literal over the
    per-field vars, matching the pre-split serialized router shape.
    """
    prefix = "reflex___state____state"
    assert str(rx.State.router) == (
        "({ "
        f'"session": {prefix}.rx_router_session_rx_state_, '
        f'"headers": {prefix}.rx_router_headers_rx_state_, '
        f'"page": {prefix}.rx_router_page_rx_state_, '
        f'"url": {prefix}.rx_router_url_rx_state_, '
        f'"route_id": {prefix}.rx_router_route_id_rx_state_'
        " })"
    )


def test_router_var_shape_matches_the_serializer():
    """The composed router literal and the serializer must emit the same keys.

    Rendering `State.router` as a whole has to produce the object shape the
    backend serializes a `RouterData` into, or a component reading the whole
    router would see different keys from the ones the delta carries. The two
    are built in different places, so pin them to each other.
    """
    import json

    from reflex_base.utils.format import json_dumps

    from reflex.istate.data import RouterData, serialize_router_data

    rendered_keys = list(rx.State.router._wire_fields())
    assert rendered_keys == list(serialize_router_data(RouterData()))
    # And that is what actually reaches the client for a whole-router value.
    assert rendered_keys == list(json.loads(json_dumps(RouterData())))


def test_router_var_carries_state_var_data():
    """The switchboard var must merge the per-field vars' VarData so hooks
    and context wiring for the root state are set up when it renders.
    """
    var_data = rx.State.router._get_all_var_data()
    assert var_data is not None
    assert var_data.state == rx.State.get_full_name()


@pytest.mark.parametrize("attr", ["path", "scheme", "netloc", "query", "fragment"])
def test_reflex_url_rejects_attribute_assignment(attr: str):
    """A parsed component must not be assignable.

    `URLData.href` defaults to a class-level `ReflexURL("")`, so the empty URL
    object is shared by every state that has not navigated yet. If a component
    could be assigned, writing through one state's `router.url` would rewrite
    that shared object for all of them.
    """
    url = ReflexURL(SAMPLE_URL)
    before = getattr(url, attr)

    with pytest.raises(AttributeError, match="immutable"):
        setattr(url, attr, "/mutated")
    with pytest.raises(AttributeError, match="immutable"):
        delattr(url, attr)

    assert getattr(url, attr) == before


def test_shared_empty_url_default_cannot_be_mutated_through_a_state():
    """Writing through one state's router.url must not leak into another."""
    from reflex.istate.data import URLData
    from reflex.state import BaseState

    # A root state, so the router fields live on the instance under test
    # rather than being delegated to a parent that is not in a tree here.
    class _URLIsolationState(BaseState):
        pass

    one = _URLIsolationState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    two = _URLIsolationState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]

    with pytest.raises(AttributeError, match="immutable"):
        one.router.url.path = "/mutated"

    one.rx_router_url = URLData.from_url(ReflexURL("https://example.com/real"))

    assert one.router.url.path == "/real"
    assert two.router.url.path == ""
    assert cast("ReflexURL", URLData().href).path == ""


def test_url_data_default_matches_the_parsed_empty_url():
    """`URLData()` must equal `URLData.from_url(ReflexURL(""))`.

    The two are different construction paths to the same "not navigated yet"
    value: the dataclass defaults back every fresh state, while `from_url` is
    what `__reduce__` rebuilds a persisted one through. Written out by hand the
    defaults drifted -- `ReflexURL("").origin` is "://", not "" -- so a state
    reported one origin before a save and another after.
    """
    from reflex.istate.data import URLData

    assert URLData() == URLData.from_url(ReflexURL(""))


@pytest.mark.parametrize(
    "raw",
    [
        "",
        SAMPLE_URL,
        "http://x/",
        "https://a.b/c?d=1&d=2#f",
    ],
)
def test_reflex_url_and_url_data_survive_pickling(raw: str):
    """Both persist through a pickle round-trip with every component intact.

    `ReflexURL` and `URLData` persist only the URL itself and re-split it on
    the way back, so this pins that the derived components come back equal
    rather than being silently dropped or recomputed differently.
    """
    import pickle

    from reflex.istate.data import URLData

    components = ("scheme", "netloc", "origin", "path", "query", "fragment")

    url = ReflexURL(raw)
    restored_url = pickle.loads(pickle.dumps(url))
    assert type(restored_url) is ReflexURL
    assert str(restored_url) == raw
    for component in components:
        assert getattr(restored_url, component) == getattr(url, component)
    assert dict(restored_url.query_parameters) == dict(url.query_parameters)

    data = URLData.from_url(url)
    restored_data = pickle.loads(pickle.dumps(data))
    assert restored_data == data
    # The runtime href must still be a ReflexURL, or backend component access
    # through `self.router.url` breaks after a state is loaded from the store.
    assert isinstance(restored_data.href, ReflexURL)


def test_pickling_a_url_does_not_store_its_derived_components():
    """The persisted form must carry the URL once, not every parsed piece.

    `URLData` is the storage form of a router var, so it is pickled on every
    state write. Storing the seven derived components alongside `href` wrote
    the URL into the state store eight times over.
    """
    import pickle

    from reflex.istate.data import URLData

    blob = pickle.dumps(URLData.from_url(ReflexURL(SAMPLE_URL)))
    # Every component is derivable from the href, so the href is the only
    # occurrence of the URL text in the payload.
    assert blob.count(b"example.com") == 1
    assert b"query_parameters" not in blob


def test_reflex_url_query_parameter_named_self():
    """A query parameter called ``self`` is kept like any other.

    The parsed parameters are passed to the frozen mapping as keyword
    arguments, so a ``self`` key must not collide with the constructor's own
    ``self`` argument and crash router URL parsing for that page.
    """
    url = ReflexURL("https://example.com/post?self=1&id=2")
    assert dict(url.query_parameters) == {"self": "1", "id": "2"}


def test_header_data_keeps_raw_header_named_self():
    """A request header called ``self`` is kept in ``raw_headers``."""
    from reflex_base import constants

    from reflex.istate.data import HeaderData

    headers = HeaderData.from_router_data({
        constants.RouteVar.HEADERS: {"self": "x", "origin": "http://localhost:3000"}
    })
    assert headers.raw_headers["self"] == "x"
    assert headers.origin == "http://localhost:3000"
