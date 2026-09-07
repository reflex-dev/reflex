"""Tests for reflex_base.utils.types."""

import collections
import dataclasses
import datetime
import enum
import types
import typing
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, TypedDict, TypeVar

import pytest
import wrapt
from reflex_base.utils.types import (
    _RUNTIME_VALIDATORS,
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
    _isinstance,
    resolve_type_alias,
    runtime_isinstance,
    typehint_issubclass,
)
from typing_extensions import ParamSpec, TypeAliasType, TypeVarTuple, Unpack

P = ParamSpec("P")
Ts = TypeVarTuple("Ts")
Handlers = TypeAliasType(
    "Handlers", tuple[Callable[P, int], Unpack[Ts]], type_params=(P, Ts)
)


def _type_alias_types() -> list[type]:
    """Collect the TypeAliasType classes available on this Python.

    Returns:
        The typing_extensions class, plus the distinct native ``typing`` class
        on 3.12+ (the two produce separate alias objects there).
    """
    native = getattr(typing, "TypeAliasType", None)
    return (
        [TypeAliasType] if native in (None, TypeAliasType) else [TypeAliasType, native]
    )


def test_asgi_aliases_keep_their_names():
    """The ASGI type aliases are TypeAliasTypes so docs render them by name, not expanded."""
    for alias in (Scope, Message, Receive, Send, ASGIApp):
        assert isinstance(alias, TypeAliasType)

    assert Scope.__name__ == "Scope"
    assert Message.__name__ == "Message"
    assert Receive.__name__ == "Receive"
    assert Send.__name__ == "Send"
    assert ASGIApp.__name__ == "ASGIApp"


def test_resolve_type_alias_substitutes_param_spec():
    """A ParamSpec is substituted even next to a TypeVarTuple.

    That combination falls back to manual substitution on 3.10 and 3.11, which
    has to treat a ParamSpec as a type parameter too.
    """
    resolved = resolve_type_alias(Handlers[[str], bool, float])
    assert resolved == tuple[Callable[[str], int], bool, float]


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_isinstance_resolves_type_alias(alias_cls: type) -> None:
    """_isinstance unwraps a TypeAliasType annotation instead of raising.

    State.__setattr__ validates assignments against the raw field annotation,
    so an alias like ``type Key = Literal["a", "b"]`` must resolve rather than
    reach the bare ``isinstance`` call, which rejects a TypeAliasType.
    """
    name = alias_cls("Name", str)
    key = alias_cls("Key", Literal["a", "b"])
    t = TypeVar("t")
    items = alias_cls("Items", list[t], type_params=(t,))  # pyright: ignore[reportGeneralTypeIssues]

    assert _isinstance("y", name, nested=1, treat_var_as_type=False)
    assert not _isinstance(1, name, nested=1, treat_var_as_type=False)
    assert _isinstance("b", key, nested=1, treat_var_as_type=False)
    assert not _isinstance("c", key, nested=1, treat_var_as_type=False)
    assert _isinstance(["z"], items[str], nested=1, treat_var_as_type=False)
    assert not _isinstance([1], items[str], nested=1, treat_var_as_type=False)
    assert _isinstance(None, key | None, nested=1, treat_var_as_type=False)
    assert _isinstance("a", key | None, nested=1, treat_var_as_type=False)
    assert not _isinstance("c", key | None, nested=1, treat_var_as_type=False)

    maybe = alias_cls("Maybe", str | None)
    assert _isinstance(None, maybe, nested=1, treat_var_as_type=False)
    assert _isinstance("x", maybe, nested=1, treat_var_as_type=False)
    assert not _isinstance(1, maybe, nested=1, treat_var_as_type=False)


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_typehint_issubclass_resolves_type_alias(alias_cls: type) -> None:
    """typehint_issubclass resolves TypeAliasType on either side.

    Event triggers compare their provided types against handler annotations,
    so an alias-annotated handler arg must resolve instead of reaching the
    bare ``issubclass`` call or failing the origin comparison.
    """
    name = alias_cls("Name", str)
    key = alias_cls("Key", Literal["a", "b"])
    k = TypeVar("k")
    v = TypeVar("v")
    pair = alias_cls("Pair", dict[k, v], type_params=(k, v))  # pyright: ignore[reportGeneralTypeIssues]

    assert typehint_issubclass(str, name)
    assert not typehint_issubclass(int, name)
    assert typehint_issubclass(name, str)
    assert typehint_issubclass(str, key)
    assert not typehint_issubclass(int, key)
    assert typehint_issubclass(key, str)
    assert typehint_issubclass(pair[str, str], dict[str, str])
    assert typehint_issubclass(dict[str, str], pair[str, str])
    assert not typehint_issubclass(pair[str, int], dict[str, str])
    assert typehint_issubclass(str, key | None)
    assert typehint_issubclass(key | None, str | None)
    assert not typehint_issubclass(key | None, str)

    # An alias of a union must compare with union semantics on either side.
    maybe = alias_cls("Maybe", str | None)
    assert typehint_issubclass(maybe, str | None)
    assert typehint_issubclass(str | None, maybe)
    assert typehint_issubclass(maybe, maybe)
    assert not typehint_issubclass(maybe, str)
    assert typehint_issubclass(str, maybe)


class _Point(TypedDict):
    x: int


@dataclasses.dataclass
class _Row:
    a: int


class _Color(enum.Enum):
    RED = 1


class _Text(str):
    pass


_RUNTIME_HINTS = [
    int,
    float,
    str,
    bool,
    None,
    Any,
    object,
    _Row,
    _Color,
    _Point,
    _Text,
    list,
    dict,
    list[int],
    list[float],
    list[str],
    list[_Row],
    list[_Point],
    list[list[int]],
    list[Any],
    list[object],
    list[int | None],
    list[_Row | None],
    list[Literal["a", "b"]],
    dict[str, int],
    dict[int, list[int]],
    tuple[int, ...],
    tuple[int, str],
    tuple[()],
    set[int],
    frozenset[int],
    int | None,
    int | str,
    Literal[1, "a"],
    Sequence[int],
    Mapping[str, int],
    collections.OrderedDict[str, int],
    type[_Row],
    datetime.datetime,
    list[datetime.date],
]

_RUNTIME_VALUES = [
    1,
    1.5,
    True,
    "a",
    _Text("a"),
    None,
    _Row(1),
    _Color.RED,
    {"x": 1},
    {"x": "s"},
    {},
    [],
    [1, 2],
    [1.0],
    [1, "a"],
    [True],
    [_Row(1)],
    [_Row(1), None],
    [[1]],
    [[1], ["a"]],
    [None, 1],
    (1, 2),
    (1, "a"),
    (),
    {1, 2},
    frozenset({1}),
    {"a": 1},
    {"a": "b"},
    {1: [1]},
    collections.OrderedDict(a=1),
    types.MappingProxyType({"a": 1}),
    ["a", "b"],
    ["c"],
    [object()],
    _Row,
    [_Row],
    datetime.datetime(2024, 1, 1),
    [datetime.date(2024, 1, 1)],
]


@pytest.mark.parametrize("hint", _RUNTIME_HINTS, ids=repr)
def test_runtime_isinstance_matches_isinstance(hint: Any):
    """The compiled check agrees with ``_isinstance`` for every value.

    Args:
        hint: The declared type to check against.
    """
    for value in _RUNTIME_VALUES:
        expected = _isinstance(value, hint, nested=1, treat_var_as_type=False)
        assert runtime_isinstance(value, hint) is expected, (value, hint)


def test_runtime_isinstance_var_hints_and_values():
    """Var hints and Var values keep the ``_isinstance`` semantics."""
    from reflex_base.vars import Field, LiteralVar, Var

    var = Var("x")
    literal = LiteralVar.create(3)
    hints = [
        Var,
        Var[int],
        int | Var,
        list[Var],
        list[Var[int]],
        Field[int],
        Field[list[int]],
    ]
    values = [*_RUNTIME_VALUES, var, literal, [var], [literal]]
    for hint in hints:
        for value in values:
            expected = _isinstance(value, hint, nested=1, treat_var_as_type=False)
            assert runtime_isinstance(value, hint) is expected, (value, hint)
    for hint in _RUNTIME_HINTS:
        for value in (var, literal, [var], [literal]):
            expected = _isinstance(value, hint, nested=1, treat_var_as_type=False)
            assert runtime_isinstance(value, hint) is expected, (value, hint)


def test_runtime_isinstance_compiles_once_and_falls_back():
    """Supported hints compile to a cached validator; others record a fallback."""
    for hint in (list[int], dict[str, _Row], tuple[int, ...], int | None):
        runtime_isinstance([], hint)
        assert _RUNTIME_VALIDATORS[hint] is not None
    # Key-level TypedDict checks and non-dict mappings have no schema equivalent.
    for hint in (_Point, Mapping[str, int], object):
        runtime_isinstance({}, hint)
        assert _RUNTIME_VALIDATORS[hint] is None


def test_runtime_isinstance_unwraps_proxies():
    """State reads hand back wrapt proxies; they must validate as their value."""
    for value, hint in [
        ([_Row(1)], list[_Row]),
        ({"a": 1}, dict[str, int]),
        ((1, 2), tuple[int, ...]),
        ({1}, set[int]),
        (_Row(1), _Row),
    ]:
        proxied = wrapt.ObjectProxy(value)
        assert runtime_isinstance(proxied, hint)
        assert runtime_isinstance([proxied], list[hint])  # pyright: ignore[reportInvalidTypeForm]
        assert not runtime_isinstance(wrapt.ObjectProxy(["x"]), list[_Row])
