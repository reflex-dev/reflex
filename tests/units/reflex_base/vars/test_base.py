"""Tests for reflex_base.vars.base state metaclass field handling."""

import threading
import typing
from typing import Any, Literal, TypeVar

import pytest
from reflex_base.utils.types import get_field_type
from reflex_base.vars.base import EvenMoreBasicBaseState, Var, field
from reflex_base.vars.object import ObjectVar
from reflex_base.vars.sequence import ArrayVar, StringVar
from typing_extensions import TypeAliasType, TypeVarTuple, Unpack

from reflex.state import State

_MARKER_ATTR = "_marker"


def test_custom_field_attr_survives_annotated_rebuild():
    """A custom attribute on an annotated Field survives a rebuild."""
    f = field("x")
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is str


def test_custom_field_attr_survives_unannotated_rebuild():
    """A custom attribute survives an inferred-type Field rebuild."""
    f = field(0)
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        count = f

    rebuilt = MyState.get_fields()["count"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is int


def test_custom_field_attr_survives_unannotated_factory_rebuild():
    """A custom attribute survives a default-factory Field rebuild."""
    f = field(default_factory=list)
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        items = f

    rebuilt = MyState.get_fields()["items"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is Any


def test_reserved_annotation_attr_not_copied():
    """A custom `annotation` attr must not make the rebuilt Field look pydantic.

    get_field_type duck-types __fields__ entries on `.annotation`, so copying
    it would shadow the real class annotation.
    """
    f = field("x")
    f.annotation = int  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert "annotation" not in rebuilt.__dict__
    assert get_field_type(MyState, "name") is str


def test_custom_attr_is_carried_by_reference():
    """Custom attrs land on the rebuilt Field as the same objects.

    Identity is what tag consumers rely on (e.g. stateful callable markers
    must not run as clones), and any copy scheme would break it. The lock
    also guards the old failure mode directly: deep-copying carried attrs
    raised ``TypeError: cannot pickle '_thread.lock' object``.
    """

    class Check:
        def __init__(self) -> None:
            self.lock = threading.Lock()

    check = Check()
    f = field("x")
    f._check = check  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert rebuilt._check is check  # pyright: ignore[reportAttributeAccessIssue]


def _type_alias_types() -> list[type]:
    native = getattr(typing, "TypeAliasType", None)
    return (
        [TypeAliasType] if native in (None, TypeAliasType) else [TypeAliasType, native]
    )


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_guess_type_resolves_type_alias(alias_cls: type) -> None:
    """A TypeAliasType (PEP 695 ``type`` statement) resolves to its value.

    State var annotations like ``type Key = Literal[...]`` reach guess_type as
    a TypeAliasType, which must be unwrapped instead of raising TypeError.
    """
    alias = alias_cls("ChartKey", Literal["day", "week"])

    var = Var(_js_expr="key", _var_type=alias).guess_type()
    assert isinstance(var, StringVar)
    assert var._var_type == Literal["day", "week"]

    optional_var = Var(_js_expr="key", _var_type=alias | None).guess_type()
    assert isinstance(optional_var, StringVar)


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_guess_type_resolves_parameterized_type_alias(alias_cls: type) -> None:
    """A subscripted generic alias (``type Keys[T] = list[T]``) resolves.

    The subscription keeps the TypeAliasType as the origin, so resolution has
    to substitute the alias's type parameters into its value.
    """
    t = TypeVar("t")
    keys = alias_cls("Keys", list[t], type_params=(t,))  # pyright: ignore[reportGeneralTypeIssues]

    var = Var(_js_expr="keys", _var_type=keys[str]).guess_type()
    assert isinstance(var, ArrayVar)
    assert var._var_type == list[str]

    optional_var = Var(_js_expr="keys", _var_type=keys[str] | None).guess_type()
    assert isinstance(optional_var, ArrayVar)

    k = TypeVar("k")
    v = TypeVar("v")
    # value's __parameters__ order (v, k) differs from type_params (k, v)
    pair = alias_cls("Pair", dict[v, k], type_params=(k, v))  # pyright: ignore[reportGeneralTypeIssues]
    pair_var = Var(_js_expr="pair", _var_type=pair[str, int]).guess_type()
    assert isinstance(pair_var, ObjectVar)
    assert pair_var._var_type == dict[int, str]


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_guess_type_resolves_variadic_type_alias(alias_cls: type) -> None:
    """A variadic alias (``type Tup[*Ts] = tuple[*Ts]``) keeps all arguments.

    The TypeVarTuple must absorb every remaining subscription argument, not
    just the one a plain positional zip would pair it with.
    """
    ts = TypeVarTuple("ts")
    tup = alias_cls("Tup", tuple[Unpack[ts]], type_params=(ts,))  # pyright: ignore[reportGeneralTypeIssues]
    var = Var(_js_expr="t", _var_type=tup[str, int]).guess_type()
    assert isinstance(var, ArrayVar)
    assert var._var_type == tuple[str, int]

    t = TypeVar("t")
    prefixed = alias_cls("Prefixed", dict[t, tuple[Unpack[ts]]], type_params=(t, ts))  # pyright: ignore[reportGeneralTypeIssues]
    prefixed_var = Var(_js_expr="p", _var_type=prefixed[str, int, float]).guess_type()
    assert isinstance(prefixed_var, ObjectVar)
    assert prefixed_var._var_type == dict[str, tuple[int, float]]

    suffixed = alias_cls("Suffixed", dict[t, tuple[Unpack[ts]]], type_params=(ts, t))  # pyright: ignore[reportGeneralTypeIssues]
    suffixed_var = Var(_js_expr="s", _var_type=suffixed[int, float, str]).guess_type()
    assert isinstance(suffixed_var, ObjectVar)
    assert suffixed_var._var_type == dict[str, tuple[int, float]]


@pytest.mark.parametrize("alias_cls", _type_alias_types())
def test_state_var_type_alias(alias_cls: type) -> None:
    """A state var annotated with a TypeAliasType compiles."""
    chart_key = alias_cls("ChartKey", Literal["day", "week"])

    class TypeAliasState(State):
        key: chart_key = "day"  # pyright: ignore[reportInvalidTypeForm]

    assert isinstance(TypeAliasState.key, StringVar)
    assert TypeAliasState.key._var_type == Literal["day", "week"]
