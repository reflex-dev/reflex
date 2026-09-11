"""Tests for reflex_base.vars.base state metaclass field handling."""

import dataclasses
import threading
import traceback
import typing
from collections.abc import Callable
from typing import Any, Literal, TypeVar

import pytest
from reflex_base.utils import serializers
from reflex_base.utils.types import get_field_type
from reflex_base.vars.base import (
    CachedVarOperation,
    EvenMoreBasicBaseState,
    LiteralVar,
    Var,
    VarData,
    _linearize_bases,
    cached_property_no_lock,
    field,
)
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


@pytest.mark.parametrize(
    "shape",
    [
        "single",
        "diamond",
        "shared_via_two_bases",
        "base_of_a_base",
        "three_bases",
        "ancestor_listed_after_descendant",
    ],
)
def test_linearize_bases_matches_real_mro(shape: str) -> None:
    """The pre-creation linearization equals the MRO `type` builds.

    Args:
        shape: The inheritance shape to build.
    """
    a = type("A", (), {})
    b = type("B", (a,), {})
    c = type("C", (a,), {})
    d = type("D", (), {})
    bases: tuple[type, ...] = {
        "single": (b,),
        "diamond": (b, c),
        "shared_via_two_bases": (type("E", (b,), {}), type("F", (c,), {})),
        "base_of_a_base": (b, a),
        "three_bases": (b, c, d),
        # C3 keeps `a` ahead of `d` here, though `d` sits earlier in the first
        # base's own MRO
        "ancestor_listed_after_descendant": (type("G", (a, d), {}), a),
    }[shape]

    created = type("Created", bases, {})
    assert _linearize_bases(bases) == list(created.__mro__[1:])


def test_linearize_bases_without_bases() -> None:
    """A class with no bases has nothing to inherit from."""
    assert _linearize_bases(()) == []


def test_linearize_bases_compares_by_identity() -> None:
    """A metaclass defining __eq__ must not confuse the linearization."""

    class EqMeta(type):
        def __eq__(cls, other: object) -> bool:
            return True

        def __hash__(cls) -> int:
            return 1

    a = EqMeta("A", (), {})
    b = EqMeta("B", (a,), {})
    c = EqMeta("C", (a,), {})
    created = EqMeta("Created", (b, c), {})

    # `==` between these classes is always True, so compare element identities
    assert all(
        left is right
        for left, right in zip(
            _linearize_bases((b, c)), created.__mro__[1:], strict=True
        )
    )


_REAL_ERROR = "the real error"


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class _BrokenVarData(CachedVarOperation, Var):
    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return "broken"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        raise AttributeError(_REAL_ERROR)


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class _BrokenVarName(CachedVarOperation, Var):
    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        raise AttributeError(_REAL_ERROR)


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class _BrokenObjectVarName(CachedVarOperation, ObjectVar):
    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        raise AttributeError(_REAL_ERROR)


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class _OuterVarName(CachedVarOperation, Var):
    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        return str(_BrokenVarName(_js_expr=""))


@dataclasses.dataclass(eq=False, frozen=True, slots=True)
class _ValueErrorVarName(CachedVarOperation, Var):
    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        raise ValueError(_REAL_ERROR)


@pytest.mark.parametrize(
    ("access", "property_name"),
    [
        pytest.param(
            lambda: _BrokenVarData(_js_expr="")._get_all_var_data(),
            "_BrokenVarData._cached_get_all_var_data",
            id="get_all_var_data",
        ),
        pytest.param(
            lambda: str(_BrokenVarName(_js_expr="")),
            "_BrokenVarName._cached_var_name",
            id="str",
        ),
        pytest.param(
            lambda: _BrokenVarName(_js_expr="")._js_expr,
            "_BrokenVarName._cached_var_name",
            id="js_expr",
        ),
        pytest.param(
            lambda: str(_BrokenObjectVarName(_js_expr="", _var_type=dict)),
            "_BrokenObjectVarName._cached_var_name",
            id="mapping_object_var",
        ),
        # the outer property sees a RuntimeError, so the error is wrapped once
        pytest.param(
            lambda: str(_OuterVarName(_js_expr="")),
            "_BrokenVarName._cached_var_name",
            id="nested",
        ),
    ],
)
def test_cached_property_attribute_error_is_chained(
    access: Callable[[], object], property_name: str
) -> None:
    """An AttributeError raised while computing a cached property is not masked.

    CPython would otherwise treat it as a failed lookup and fall back to
    ``__getattr__``, which reported a bogus missing attribute or, for Mapping
    vars, fabricated an item access.

    Args:
        access: Triggers the failing cached property.
        property_name: The class and attribute name of the failing property.
    """
    with pytest.raises(RuntimeError) as exc_info:
        access()
    assert str(exc_info.value) == (
        f"Computing cached property {property_name} raised AttributeError: {_REAL_ERROR}"
    )
    cause = exc_info.value.__cause__
    assert type(cause) is AttributeError
    assert str(cause) == _REAL_ERROR


def test_cached_property_other_errors_propagate_unwrapped() -> None:
    """Exceptions other than AttributeError keep their type and have no cause."""
    with pytest.raises(ValueError, match=_REAL_ERROR) as exc_info:
        str(_ValueErrorVarName(_js_expr=""))
    assert exc_info.type is ValueError
    assert exc_info.value.__cause__ is None


def test_cached_property_failure_is_not_cached() -> None:
    """A failed computation runs again on the next access, then caches."""
    attempts = []

    @dataclasses.dataclass(eq=False, frozen=True, slots=True)
    class FlakyVar(CachedVarOperation, Var):
        @cached_property_no_lock
        def _cached_var_name(self) -> str:
            attempts.append(None)
            if len(attempts) == 1:
                raise AttributeError(_REAL_ERROR)
            return "recovered"

    var = FlakyVar(_js_expr="")
    with pytest.raises(RuntimeError):
        str(var)
    assert str(var) == "recovered"
    assert str(var) == "recovered"
    assert len(attempts) == 2


def test_serializer_attribute_error_is_not_masked() -> None:
    """A typo in a user serializer surfaces with the serializer's own frame."""

    class Point:
        pass

    def serialize_point(value: Point) -> str:
        return value.label  # pyright: ignore[reportAttributeAccessIssue]

    serializers.serializer(serialize_point)
    try:
        with pytest.raises(
            RuntimeError, match=r"LiteralArrayVar\._cached_var_name"
        ) as exc_info:
            str(LiteralVar.create([Point()]))
    finally:
        serializers.SERIALIZERS.pop(Point)
        serializers.SERIALIZER_TYPES.pop(Point)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()
    cause = exc_info.value.__cause__
    assert isinstance(cause, AttributeError)
    assert "'label'" in str(cause)
    frames = traceback.extract_tb(cause.__traceback__)
    assert frames[-1].name == serialize_point.__name__
