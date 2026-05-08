"""This module contains the dataclasses representing the router object."""

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import _NetlocResultMixinStr, parse_qsl, urlsplit

from reflex_base import constants
from reflex_base.utils import console, format
from reflex_base.utils.serializers import serializer
from reflex_base.vars.base import (
    CachedVarOperation,
    Var,
    VarData,
    VarSubclassEntry,
    _var_subclasses,
    cached_property_no_lock,
)
from reflex_base.vars.object import ObjectItemOperation, ObjectVar
from reflex_base.vars.sequence import StringVar


@dataclasses.dataclass(frozen=True, init=False)
class _FrozenDictStrStr(Mapping[str, str]):
    _data: MappingProxyType[str, str]

    def __init__(self, **kwargs):
        object.__setattr__(
            self, "_data", MappingProxyType(dict(sorted(kwargs.items())))
        )

    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __hash__(self) -> int:
        return hash(frozenset(self._data.items()))

    def __getstate__(self) -> object:
        return dict(self._data)

    def __setstate__(self, state: object) -> None:
        if not isinstance(state, dict):
            msg = "Invalid state for _FrozenDictStrStr"
            raise TypeError(msg)
        object.__setattr__(self, "_data", MappingProxyType(state))


@dataclasses.dataclass(frozen=True)
class _HeaderData:
    host: str = ""
    origin: str = ""
    upgrade: str = ""
    connection: str = ""
    cookie: str = ""
    pragma: str = ""
    cache_control: str = ""
    user_agent: str = ""
    sec_websocket_version: str = ""
    sec_websocket_key: str = ""
    sec_websocket_extensions: str = ""
    accept_encoding: str = ""
    accept_language: str = ""
    raw_headers: Mapping[str, str] = dataclasses.field(
        default_factory=_FrozenDictStrStr
    )


_HEADER_DATA_FIELDS = frozenset([
    field.name for field in dataclasses.fields(_HeaderData)
])


@dataclasses.dataclass(frozen=True)
class HeaderData(_HeaderData):
    """An object containing headers data."""

    @classmethod
    def from_router_data(cls, router_data: dict) -> "HeaderData":
        """Create a HeaderData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A HeaderData object initialized with the provided router_data.
        """
        return cls(
            **{
                snake_case_key: v
                for k, v in router_data.get(constants.RouteVar.HEADERS, {}).items()
                if v
                and (snake_case_key := format.to_snake_case(k)) in _HEADER_DATA_FIELDS
            },
            raw_headers=_FrozenDictStrStr(**{
                k: v
                for k, v in router_data.get(constants.RouteVar.HEADERS, {}).items()
                if v
            }),
        )


@serializer(to=dict)
def _serialize_header_data(obj: HeaderData) -> dict:
    return {k.name: getattr(obj, k.name) for k in dataclasses.fields(obj)}


@serializer(to=dict)
def serialize_frozen_dict_str_str(obj: _FrozenDictStrStr) -> dict:
    """Serialize a _FrozenDictStrStr object to a dict.

    Args:
        obj: the _FrozenDictStrStr object.

    Returns:
        A dict representation of the _FrozenDictStrStr object.
    """
    return dict(obj._data)


class ReflexURL(str, _NetlocResultMixinStr):
    """A class representing a URL split result."""

    if TYPE_CHECKING:
        scheme: str
        netloc: str
        origin: str
        path: str
        query: str
        query_parameters: Mapping[str, str]
        fragment: str

    def __new__(cls, url: str):
        """Create a new ReflexURL instance.

        Args:
            url: the URL to split.

        Returns:
            A new ReflexURL instance.
        """
        (scheme, netloc, path, query, fragment) = urlsplit(url)
        obj = super().__new__(cls, url)
        object.__setattr__(obj, "scheme", scheme)
        object.__setattr__(obj, "netloc", netloc)
        object.__setattr__(obj, "path", path)
        object.__setattr__(obj, "query", query)
        object.__setattr__(obj, "origin", f"{scheme}://{netloc}")
        object.__setattr__(
            obj, "query_parameters", _FrozenDictStrStr(**dict(parse_qsl(query)))
        )
        object.__setattr__(obj, "fragment", fragment)
        return obj


@serializer(to=dict)
def _serialize_reflex_url(obj: ReflexURL) -> dict:
    """Serialize a ReflexURL to an object with its parsed components.

    The full URL is exposed under the ``href`` key so the frontend can read
    either the whole URL or any individual component without re-parsing.

    Args:
        obj: the ReflexURL to serialize.

    Returns:
        A dict with scheme, netloc, origin, path, query, query_parameters,
        fragment, and href.
    """
    return {
        "scheme": obj.scheme,
        "netloc": obj.netloc,
        "origin": obj.origin,
        "path": obj.path,
        "query": obj.query,
        "query_parameters": dict(obj.query_parameters),
        "fragment": obj.fragment,
        "href": str.__str__(obj),
    }


class ReflexURLVar(StringVar[ReflexURL]):
    """Var type marker for ReflexURL.

    Exists only to anchor the type registration for ``ReflexURL``; actual
    instances returned by the Var system are always ``ReflexURLCastedVar``,
    which exposes URL components as typed properties.
    """


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ReflexURLCastedVar(CachedVarOperation, ReflexURLVar):
    """Cast-to-ReflexURL operation whose default rendering reads ``href``.

    Constructed when ``guess_type`` / ``to(ReflexURLVar)`` is invoked on any
    Var typed as ReflexURL (e.g. ``State.router.url``). Its top-level JS
    expression is ``{original}?.["href"]`` so string-context usage produces
    the full URL; component access via the typed properties below reads the
    matching key on ``{original}`` instead.
    """

    _original: Var = dataclasses.field(
        default_factory=lambda: Var(_js_expr="null", _var_type=None),
    )
    _default_var_type: ClassVar[Any] = ReflexURL

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """Render the URL as its ``href`` string in JS.

        Returns:
            The JS expression for the full URL string.
        """
        return f'{self._original!s}?.["href"]'

    def _component(self, name: str) -> Var:
        """Build an indexing operation for a key on the serialized URL object.

        The returned Var is untyped; each property wraps this in a
        ``.to(...)`` call to narrow it to the correct Var subclass.

        Args:
            name: The component key on the serialized URL object.

        Returns:
            A Var reading ``name`` from the URL object.
        """
        return ObjectItemOperation.create(
            self._original.to(ObjectVar, Mapping[str, Any]),
            name,
        )

    @property
    def scheme(self) -> StringVar:
        """The URL scheme (e.g. ``"https"``).

        Returns:
            StringVar accessing ``scheme`` on the serialized URL.
        """
        return self._component("scheme").to(str)

    @property
    def netloc(self) -> StringVar:
        """The network location, including host and optional port.

        Returns:
            StringVar accessing ``netloc`` on the serialized URL.
        """
        return self._component("netloc").to(str)

    @property
    def origin(self) -> StringVar:
        """The scheme and netloc joined (e.g. ``"https://example.com:3000"``).

        Returns:
            StringVar accessing ``origin`` on the serialized URL.
        """
        return self._component("origin").to(str)

    @property
    def path(self) -> StringVar:
        """The URL path as shown in the browser (no query or fragment).

        Returns:
            StringVar accessing ``path`` on the serialized URL.
        """
        return self._component("path").to(str)

    @property
    def query(self) -> StringVar:
        """The raw query string, without a leading ``?``.

        Returns:
            StringVar accessing ``query`` on the serialized URL.
        """
        return self._component("query").to(str)

    @property
    def query_parameters(self) -> ObjectVar[Mapping[str, str]]:
        """The parsed query string as a mapping.

        Returns:
            ObjectVar accessing ``query_parameters`` on the serialized URL.
        """
        return self._component("query_parameters").to(ObjectVar, Mapping[str, str])

    @property
    def fragment(self) -> StringVar:
        """The URL fragment, without a leading ``#``.

        Returns:
            StringVar accessing ``fragment`` on the serialized URL.
        """
        return self._component("fragment").to(str)

    @classmethod
    def create(
        cls,
        value: Var,
        _var_type: Any = None,
        _var_data: VarData | None = None,
    ) -> "ReflexURLCastedVar":
        """Create a ReflexURLCastedVar wrapping another Var.

        Args:
            value: The Var being cast to ReflexURL.
            _var_type: Optional override for the var type.
            _var_data: Additional VarData to merge in.

        Returns:
            The new ReflexURLCastedVar.
        """
        return cls(
            _js_expr="",
            _var_type=_var_type or ReflexURL,
            _var_data=_var_data,
            _original=value,
        )


# ReflexURLCastedVar intentionally uses the CachedVarOperation lineage rather
# than ToOperation so _js_expr can render as {original}?.["href"]. The registry
# entry still accepts it because .to()/guess_type() only call .create(...),
# which has a compatible signature.
_var_subclasses.append(
    VarSubclassEntry(ReflexURLVar, ReflexURLCastedVar, (ReflexURL,))  # pyright: ignore[reportArgumentType]
)


@dataclasses.dataclass(frozen=True)
class PageData:
    """An object containing page data."""

    host: str = ""  # repeated with self.headers.origin (remove or keep the duplicate?)
    path: str = ""
    raw_path: str = ""
    full_path: str = ""
    full_raw_path: str = ""
    params: dict = dataclasses.field(default_factory=dict)

    @classmethod
    def from_router_data(cls, router_data: dict) -> "PageData":
        """Create a PageData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A PageData object initialized with the provided router_data.
        """
        host = router_data.get(constants.RouteVar.HEADERS, {}).get("origin", "")
        path = router_data.get(constants.RouteVar.PATH, "")
        raw_path = router_data.get(constants.RouteVar.ORIGIN, "")
        return cls(
            host=host,
            path=path,
            raw_path=raw_path,
            full_path=f"{host}{path}",
            full_raw_path=f"{host}{raw_path}",
            params=router_data.get(constants.RouteVar.QUERY, {}),
        )


@serializer(to=dict)
def _serialize_page_data(obj: PageData) -> dict:
    return {key.name: getattr(obj, key.name) for key in dataclasses.fields(obj)}


@dataclasses.dataclass(frozen=True)
class SessionData:
    """An object containing session data."""

    client_token: str = ""
    client_ip: str = ""
    session_id: str = ""

    @classmethod
    def from_router_data(cls, router_data: dict) -> "SessionData":
        """Create a SessionData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A SessionData object initialized with the provided router_data.
        """
        return cls(
            client_token=router_data.get(constants.RouteVar.CLIENT_TOKEN, ""),
            client_ip=router_data.get(constants.RouteVar.CLIENT_IP, ""),
            session_id=router_data.get(constants.RouteVar.SESSION_ID, ""),
        )


@serializer(to=dict)
def _serialize_session_data(obj: SessionData) -> dict:
    return {key.name: getattr(obj, key.name) for key in dataclasses.fields(obj)}


@dataclasses.dataclass(frozen=True)
class RouterData:
    """An object containing RouterData."""

    session: SessionData = dataclasses.field(default_factory=SessionData)
    headers: HeaderData = dataclasses.field(default_factory=HeaderData)
    _page: PageData = dataclasses.field(default_factory=PageData)
    url: ReflexURL = dataclasses.field(default=ReflexURL(""))
    route_id: str = ""

    @property
    def page(self) -> PageData:
        """Get the page data.

        Returns:
            The PageData object.
        """
        console.deprecate(
            feature_name="RouterData.page",
            reason="Use RouterData.url instead",
            deprecation_version="0.8.1",
            removal_version="1.0",
        )
        return self._page

    @classmethod
    def from_router_data(cls, router_data: dict) -> "RouterData":
        """Create a RouterData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A RouterData object initialized with the provided router_data.
        """
        return cls(
            session=SessionData.from_router_data(router_data),
            headers=HeaderData.from_router_data(router_data),
            _page=PageData.from_router_data(router_data),
            url=ReflexURL(
                router_data.get(constants.RouteVar.HEADERS, {}).get("origin", "")
                + router_data.get(constants.RouteVar.ORIGIN, "")
            ),
            route_id=router_data.get(constants.RouteVar.PATH, ""),
        )


@serializer(to=dict)
def serialize_router_data(obj: RouterData) -> dict:
    """Serialize a RouterData object to a dict.

    Args:
        obj: the RouterData object.

    Returns:
        A dict representation of the RouterData object.
    """
    return {
        "session": obj.session,
        "headers": obj.headers,
        "page": obj._page,
        # ReflexURL is a str subclass, so json.dumps handles it natively and
        # never invokes the `default=serialize` hook. Call the URL serializer
        # eagerly here so the frontend receives the parsed component dict
        # instead of just the raw URL string.
        "url": _serialize_reflex_url(obj.url),
        "route_id": obj.route_id,
    }
