"""Tests for reflex_base.vars.base state metaclass field handling."""

import asyncio
import dataclasses
import datetime
import enum
import gc
import logging
import os
import pickle
import subprocess
import sys
import threading
import traceback
import typing
import weakref
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar, Generic, Literal, Protocol, Self, TypeVar

import pytest
from reflex_base import constants
from reflex_base.constants import RouteArgType
from reflex_base.environment import _load_dotenv_from_files, environment
from reflex_base.utils import serializers
from reflex_base.utils.exceptions import (
    BackendVarFormatError,
    ReflexRuntimeError,
    StateValueError,
    UntypedVarError,
)
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import get_field_type
from reflex_base.vars.base import (
    _ABC_BOOKKEEPING_NAME,
    FIELD_TYPE,
    GLOBAL_CACHE,
    BaseStateMeta,
    CachedVarOperation,
    EvenMoreBasicBaseState,
    Field,
    LiteralVar,
    Var,
    VarData,
    _global_vars,
    _linearize_bases,
    _type_check_depth,
    cached_property,
    cached_property_no_lock,
    computed_var,
    field,
    var_operation,
    var_operation_return,
)
from reflex_base.vars.number import NumberVar
from reflex_base.vars.object import ObjectVar
from reflex_base.vars.sequence import ArrayVar, StringVar
from typing_extensions import TypeAliasType, TypeVarTuple

from reflex.istate.proxy import MutableProxy
from reflex.state import BaseState, State, _override_base_method

_MARKER_ATTR = "_marker"


@pytest.mark.parametrize("mutable", [False, True])
@pytest.mark.parametrize("name", ["_value", "value"])
def test_class_assignment_preserves_field(mutable: bool, name: str):
    """Changing a default preserves its descriptor and instance tracking.

    Args:
        mutable: Whether the default is mutable.
        name: The backend or frontend field name.
    """

    class ConfigState(BaseState):
        _value: str | list[str] | None = None
        value: str | list[str] | None = None

    declared = ConfigState.get_fields()[name]
    original = ConfigState()
    assert getattr(original, name) is None
    replacement = ["configured"] if mutable else "configured"
    setattr(ConfigState, name, replacement)
    assert ConfigState.__dict__[name] is declared
    assert getattr(original, name) is None

    first = ConfigState()
    second = ConfigState()
    assert getattr(first, name) == getattr(second, name) == replacement
    restored = ConfigState()
    restored.__setstate__(pickle.loads(pickle.dumps(first.__getstate__())))
    assert getattr(restored, name) == replacement

    first._clean()
    setattr(first, name, "changed")
    assert name in first.dirty_vars
    assert first._was_touched
    first.reset()
    assert getattr(first, name) == replacement
    if mutable:
        getattr(first, name).append("session-only")
        assert getattr(second, name) == replacement == ["configured"]


@pytest.mark.parametrize("name", ["_value", "value"])
@pytest.mark.parametrize("inherited", [False, True])
def test_class_assignment_sets_default_factory(name: str, inherited: bool):
    """Validate a factory once and retain its descriptor for future defaults.

    Args:
        name: The backend or frontend field name.
        inherited: Whether to configure the factory through a subclass.
    """

    class ConfigState(BaseState):
        _value: list[str] = ["old"]
        value: list[str] = ["old"]

    class Child(ConfigState):
        pass

    declared = ConfigState.get_fields()[name]
    original = ConfigState()
    assert getattr(original, name) == ["old"]
    calls = []

    def factory() -> list[str]:
        """Record calls and return a fresh mutable default.

        Returns:
            An independent configured value.
        """
        calls.append(True)
        return ["new"]

    setattr(Child if inherited else ConfigState, name, factory)
    assert calls == [True]
    assert ConfigState.get_fields()[name] is Child.get_fields()[name] is declared
    assert ConfigState.__dict__[name] is declared
    assert declared.default is dataclasses.MISSING
    assert declared.default_factory is factory
    assert name not in Child.__dict__
    assert getattr(original, name) == ["old"]

    first, second = ConfigState(), ConfigState()
    assert getattr(first, name) == getattr(second, name) == ["new"]
    assert calls == [True] * 3
    getattr(first, name).append("session")
    assert getattr(second, name) == ["new"]
    first.reset()
    assert getattr(first, name) == ["new"]
    assert calls == [True] * 4


def test_class_assignment_unwraps_mutable_proxy():
    """A proxied value read from a state instance becomes a plain default."""

    class ConfigState(BaseState):
        items: list[str] = []

    source = ConfigState()
    source.items.append("a")
    assert isinstance(source.items, MutableProxy)
    ConfigState.items = source.items
    declared = ConfigState.get_fields()["items"]
    held = declared.default_factory.args[0]  # pyright: ignore[reportFunctionMemberAccess, reportOptionalMemberAccess]
    assert type(held) is list
    assert held == ["a"]
    fresh = ConfigState()
    assert fresh.items == ["a"]
    fresh.items.append("b")
    assert source.items == ["a"]
    ref = weakref.ref(source)
    del source
    gc.collect()
    assert ref() is None


def test_class_assignment_keeps_accepted_callables():
    """A callable the field's annotation accepts is the default, not a factory."""
    calls = []

    def handler(value: int = 0) -> int:
        """Record a call that assignment must never make.

        Args:
            value: The argument a factory could not supply.

        Returns:
            The argument.
        """
        calls.append(value)
        return value

    class ConfigState(BaseState):
        _handler: Callable[[int], int] | None = None
        _factory: Callable[[], int] = int
        _anything: Any = None

    for name in ("_handler", "_factory", "_anything"):
        setattr(ConfigState, name, handler)
        assert getattr(ConfigState(), name) is handler
    assert calls == []


def test_class_assignment_accepts_type_parameter_defaults():
    """A field annotated with a type parameter checks a default against its bound."""

    class Reader(Protocol):
        def read(self) -> str: ...

    class FileReader:
        def read(self) -> str:
            """Read a fixed value.

            Returns:
                The value.
            """
            return "read"

    E = TypeVar("E")
    N = TypeVar("N", bound=int)
    R = TypeVar("R", bound=Reader)

    class GenericState(BaseState, Generic[E, N, R]):
        _value: E = None  # pyright: ignore[reportAssignmentType]
        _count: N = 0  # pyright: ignore[reportAssignmentType]
        _reader: R | None = None

    class IntState(GenericState[int, int, FileReader]):
        pass

    GenericState._reader = FileReader()  # pyright: ignore[reportAttributeAccessIssue, reportGeneralTypeIssues]
    assert IntState()._reader.read() == "read"  # pyright: ignore[reportOptionalMemberAccess]

    IntState._value = 5  # pyright: ignore[reportAttributeAccessIssue]
    assert IntState()._value == 5
    GenericState._value = "text"  # pyright: ignore[reportAttributeAccessIssue, reportGeneralTypeIssues]
    assert IntState()._value == "text"
    with pytest.raises(TypeError, match="Invalid default"):
        GenericState._count = "text"  # pyright: ignore[reportAttributeAccessIssue, reportGeneralTypeIssues]
    GenericState._count = 5  # pyright: ignore[reportAttributeAccessIssue, reportGeneralTypeIssues]
    assert IntState()._count == 5


@pytest.mark.parametrize("name", ["_value", "value"])
@pytest.mark.parametrize(
    "failure", ["wrong_type", "raises", "needs_argument", "var", "field"]
)
def test_class_assignment_rejects_invalid_factory(name: str, failure: str):
    """A failed factory validation cannot change an existing default.

    Args:
        name: The backend or frontend field name.
        failure: The invalid result or invocation failure to test.
    """

    class ConfigState(BaseState):
        _value: str = "old"
        value: str = "old"

    calls = []
    error = RuntimeError("factory failed")

    def factory() -> Any:
        """Return an invalid value or raise during validation.

        Returns:
            An invalid default.

        Raises:
            RuntimeError: When testing a failing factory invocation.
        """
        calls.append(True)
        if failure == "raises":
            raise error
        if failure == "var":
            return ConfigState.value
        if failure == "field":
            return field("new")
        return 1

    def needs_argument(value: str) -> str:
        """Require an argument that a default factory cannot supply.

        Args:
            value: A required argument.

        Returns:
            The argument.
        """
        return value

    declared = ConfigState.get_fields()[name]
    previous_default, previous_factory = declared.default, declared.default_factory
    expected = {
        "wrong_type": "Invalid default",
        "raises": "Default factory.*failed",
        "needs_argument": "Default factory.*failed",
        "var": r"ClassVar\[rx.Var\]",
        "field": "computed var",
    }[failure]
    with pytest.raises(TypeError, match=expected) as exc:
        setattr(
            ConfigState,
            name,
            needs_argument if failure == "needs_argument" else factory,
        )
    if failure == "raises":
        assert exc.value.__cause__ is error
    assert ConfigState.get_fields()[name] is declared
    assert declared.default is previous_default
    assert declared.default_factory is previous_factory
    assert getattr(ConfigState(), name) == "old"
    assert calls == ([] if failure == "needs_argument" else [True])


@pytest.mark.parametrize("name", ["_value", "value"])
def test_class_assignment_closes_coroutine_probe(name: str):
    """Close a validation coroutine while retaining supported future defaults.

    Args:
        name: The coroutine-typed backend or string-typed frontend field name.
    """

    class ConfigState(BaseState):
        _value: typing.Coroutine[Any, Any, str] | None = None
        value: str = "old"

    probes = []

    async def result() -> str:
        """Return a value when a coroutine default is awaited.

        Returns:
            The configured value.
        """
        await asyncio.sleep(0)
        return "new"

    def factory() -> typing.Coroutine[Any, Any, str]:
        """Record the created coroutine so its cleanup can be checked.

        Returns:
            A new coroutine.
        """
        coroutine = result()
        probes.append(coroutine)
        return coroutine

    if name == "value":
        with pytest.raises(TypeError, match="Invalid default"):
            setattr(ConfigState, name, factory)
        assert ConfigState().value == "old"
    else:
        setattr(ConfigState, name, factory)
        coroutine = ConfigState()._value
        assert coroutine is not None
        assert asyncio.run(coroutine) == "new"
    assert probes[0].cr_frame is None


@pytest.mark.parametrize("name", ["_value", "value"])
@pytest.mark.parametrize("replacement", ["wrong", ["wrong"], None])
def test_class_assignment_rejects_invalid_default(name: str, replacement: Any):
    """Invalid defaults cannot change the declared field or its configuration.

    Args:
        name: The backend or frontend field name.
        replacement: A value incompatible with the field's type.
    """

    class ConfigState(BaseState):
        _value: list[int] = []
        value: list[int] = []

    declared = ConfigState.get_fields()[name]
    original_factory = declared.default_factory
    with pytest.raises(TypeError, match=r"Invalid default.*list\[int\]"):
        setattr(ConfigState, name, replacement)
    assert ConfigState.get_fields()[name] is declared
    assert declared.default_factory is original_factory
    assert getattr(ConfigState(), name) == []


@pytest.mark.parametrize("name", ["_value", "value", "server_value"])
@pytest.mark.parametrize("inherited", [False, True])
@pytest.mark.parametrize(
    "kind",
    [
        "var",
        "literal",
        "bound_field",
        "field",
        "factory_field",
        "raw_field",
    ],
)
def test_class_assignment_rejects_vars_and_fields(
    name: str, kind: str, inherited: bool
):
    """Reject every Var and Field assignment without changing field bindings.

    Args:
        name: The backend or frontend field name.
        kind: The Var or Field to assign.
        inherited: Whether to assign through an inheriting state.
    """

    class SourceState(BaseState):
        _source: str = "source"
        source: str = "source"

    class ConfigState(BaseState):
        _value: Any = "old"
        value: str = "old"
        server_value: str = field(default="old", is_var=False)

    class Child(ConfigState):
        pass

    calls = []

    def factory() -> str:
        """Record an unexpected evaluation of a rejected factory.

        Returns:
            A valid default that must never be requested.
        """
        calls.append(True)
        return "new"

    replacement = {
        "var": SourceState.source,
        "literal": Var.create("literal"),
        "bound_field": SourceState.get_fields()["_source"],
        "field": field("new"),
        "factory_field": field(default_factory=factory),
        "raw_field": Field(default="new"),
    }[kind]
    declared = ConfigState.get_fields()[name]
    advice = "computed var" if "field" in kind else "ClassVar\\[rx.Var\\]"
    with pytest.raises(TypeError, match=advice):
        setattr(Child if inherited else ConfigState, name, replacement)
    assert ConfigState.get_fields()[name] is declared
    assert Child.get_fields()[name] is declared
    assert ConfigState.__dict__[name] is declared
    assert name not in Child.__dict__
    assert declared._owner is ConfigState
    assert getattr(ConfigState(), name) == "old"
    assert SourceState()._source == "source"
    assert calls == []


def test_class_assignment_allows_optional_defaults_and_var_classvars():
    """Optional defaults and explicit shared Var references remain supported."""

    class ConfigState(BaseState):
        value: Field[int | None] = field(default=1)
        reference: ClassVar[Var] = Var.create("old")

    ConfigState.reference = ConfigState.value
    ConfigState.value = None
    assert ConfigState().value is None
    assert ConfigState.reference is ConfigState.value


def test_class_assignment_preserves_shadowing_classvar():
    """A ClassVar shadowing an inherited field remains ordinary configuration."""

    class Parent(BaseState):
        _value: str = "old"

    class Child(Parent):
        _value: ClassVar[str] = "child"  # pyright: ignore[reportIncompatibleVariableOverride]

    Child._value = "new"
    assert Child._value == "new"
    assert Parent()._value == "old"


def test_backend_class_assignment_replaces_default_factory():
    """A class assignment replaces a factory without evaluating it."""
    calls = []

    def factory():
        """Count default-factory evaluations.

        Returns:
            The original default.
        """
        calls.append(True)
        return "old"

    class ConfigState(BaseState):
        _value: Any = field(default_factory=factory, is_var=False)

    ConfigState._value = "new"
    assert calls == []
    assert ConfigState()._value == "new"
    assert calls == []


def test_backend_class_assignment_inherited_field_and_classvar():
    """Assignments update the owning field, while ClassVars remain ordinary attrs."""

    class Parent(BaseState):
        _value: str = "old"
        _config: ClassVar[str] = "old"

    class Child(Parent):
        pass

    declared = Parent.get_fields()["_value"]
    Child._value = "new"
    assert "_value" not in Child.__dict__
    assert Child.get_fields()["_value"] is declared
    assert Parent()._value == "new"
    assert Child()._value == "new"
    Child._config = "child"
    assert Parent._config == "old"
    assert Child._config == "child"


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
    tup = alias_cls("Tup", tuple[*ts], type_params=(ts,))  # pyright: ignore[reportGeneralTypeIssues]
    var = Var(_js_expr="t", _var_type=tup[str, int]).guess_type()
    assert isinstance(var, ArrayVar)
    assert var._var_type == tuple[str, int]

    t = TypeVar("t")
    prefixed = alias_cls("Prefixed", dict[t, tuple[*ts]], type_params=(t, ts))  # pyright: ignore[reportGeneralTypeIssues]
    prefixed_var = Var(_js_expr="p", _var_type=prefixed[str, int, float]).guess_type()
    assert isinstance(prefixed_var, ObjectVar)
    assert prefixed_var._var_type == dict[str, tuple[int, float]]

    suffixed = alias_cls("Suffixed", dict[t, tuple[*ts]], type_params=(ts, t))  # pyright: ignore[reportGeneralTypeIssues]
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


def test_var_data_merge_collects_field_names():
    """Merging vars of one state keeps every field name, deduped and in order."""
    merged = VarData.merge(
        VarData(state="s", field_name="a"),
        VarData(state="s", field_name="b"),
        VarData(state="s", field_name="a"),
    )

    assert merged is not None
    assert dict(merged.field_dependencies) == {"s": ("a", "b")}
    # `field_name` stays the first, so existing single-field readers are intact.
    assert merged.field_name == "a"


def test_var_data_merge_keeps_field_names_of_every_state():
    """A var spanning several states keeps each state's own fields.

    Fields stay grouped by the state that owns them, so a dependency on a
    composite var tracks every field it reads rather than only those of
    whichever state happened to merge first.
    """
    merged = VarData.merge(
        VarData(state="s", field_name="a"),
        VarData(state="other", field_name="b"),
        VarData(state="s", field_name="c"),
    )

    assert merged is not None
    assert dict(merged.field_dependencies) == {"s": ("a", "c"), "other": ("b",)}
    # The fallback accessors report the first state and its first field only.
    assert merged.state == "s"
    assert merged.field_name == "a"


def test_var_data_field_dependencies_round_trip():
    """`state`/`field_name` are the shorthand for a single-field mapping."""
    assert dict(VarData(state="s", field_name="a").field_dependencies) == {"s": ("a",)}
    # A state with no named field is still recorded: many vars carry only the
    # state, for its imports and hooks, and read no field.
    assert dict(VarData(state="s").field_dependencies) == {"s": ()}
    assert dict(VarData().field_dependencies) == {}
    # The canonical form wins over the shorthand.
    assert dict(
        VarData(
            state="ignored",
            field_name="ignored",
            field_dependencies={"s": ("a",), "other": ("b",)},
        ).field_dependencies
    ) == {"s": ("a",), "other": ("b",)}


def test_var_data_field_name_reports_the_first_field():
    """`field_name` reports the first field of the first state."""
    assert VarData(field_name="a").field_name == "a"
    assert VarData(field_dependencies={"s": ("a", "b")}).field_name == "a"
    assert VarData().field_name == ""


def test_serializer_attribute_error_is_not_masked() -> None:
    """An AttributeError raised inside a serializer surfaces chained, with its own frame."""

    class Point:
        pass

    def serialize_point(value: Point) -> str:
        return value.label  # pyright: ignore[reportAttributeAccessIssue]

    serializers.serializer(serialize_point)
    try:
        with pytest.raises(ReflexRuntimeError, match=r"_cached_var_name") as exc_info:
            str(LiteralVar.create([Point()]))
    finally:
        serializers.SERIALIZERS.pop(Point)
        serializers.SERIALIZER_TYPES.pop(Point)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()
    cause = exc_info.value.__cause__
    assert isinstance(cause, AttributeError)
    assert "'label'" in str(cause)
    assert traceback.extract_tb(cause.__traceback__)[-1].name == "serialize_point"


def test_cached_var_attribute_error_is_chained() -> None:
    """An AttributeError raised in a cached var computation surfaces as the cause."""

    @dataclasses.dataclass(eq=False, frozen=True, slots=True)
    class BrokenVar(CachedVarOperation, Var):
        @cached_property_no_lock
        def _cached_var_name(self) -> str:
            return "broken"

        @cached_property_no_lock
        def _cached_get_all_var_data(self):
            msg = "the real error message"
            raise AttributeError(msg)

    with pytest.raises(ReflexRuntimeError, match="the real error message") as exc_info:
        BrokenVar(_js_expr="")._get_all_var_data()
    assert isinstance(exc_info.value.__cause__, AttributeError)
    assert str(exc_info.value.__cause__) == "the real error message"


class _CachedValue:
    """A mutable input with an explicitly resettable derived value."""

    _reflex_cache_result: object

    def __init__(self, value: str):
        """Store the input.

        Args:
            value: The value to cache.
        """
        self.value = value

    @cached_property
    def result(self) -> list[str]:
        """Return the derived value.

        Returns:
            A fresh list containing the input.
        """
        return [self.value]


def test_cached_property_identity_and_reset():
    """Local keys isolate instances and survive explicit cache resets."""
    first = _CachedValue("first")
    second = _CachedValue("second")
    result = first.result
    assert first.result is result
    assert second.result == ["second"]
    first.value = "changed"
    assert first.result is result
    GLOBAL_CACHE.clear()
    assert first.result == ["changed"]
    assert first.result is not result


def test_cached_property_pickle_does_not_reuse_another_instances_key():
    """Deserialized keys must not collide with live cache entries."""
    original = _CachedValue("original")
    assert original.result == ["original"]
    restored = pickle.loads(pickle.dumps(original))
    restored.value = "restored"
    assert restored.result == ["restored"]
    assert original.result == ["original"]


def test_cached_property_releases_entry_with_instance():
    """Destroying an instance removes its cached value."""
    value = _CachedValue("temporary")
    assert value.result == ["temporary"]
    key = value._reflex_cache_result
    reference = weakref.ref(value)
    del value
    gc.collect()
    assert reference() is None
    assert key not in GLOBAL_CACHE


def test_literal_var_dispatch_follows_later_registrations():
    """A literal class registered after a lookup wins the next lookup for its type."""

    class Coordinate:
        """A value no literal Var claims yet."""

        def __init__(self, x: int):
            """Store the coordinate.

            Args:
                x: The coordinate value.
            """
            self.x = x

    from reflex_base.utils import serializers
    from reflex_base.vars import base

    var_subclasses = len(base._var_subclasses)
    literal_subclasses = len(base._var_literal_subclasses)
    try:

        @serializers.serializer
        def serialize_coordinate(value: Coordinate) -> str:
            """Serialize a coordinate.

            Args:
                value: The coordinate.

            Returns:
                Its string form.
            """
            return f"coordinate-{value.x}"

        assert str(LiteralVar.create(Coordinate(1))) == '"coordinate-1"'

        class CoordinateVar(Var[Coordinate], python_types=Coordinate):
            """A Var holding a coordinate."""

        class LiteralCoordinateVar(LiteralVar, CoordinateVar):
            """A literal coordinate Var."""

            @classmethod
            def create(cls, value: Coordinate, _var_data=None):
                """Create the literal.

                Args:
                    value: The coordinate.
                    _var_data: Unused metadata.

                Returns:
                    A Var with the coordinate's expression.
                """
                return Var(_js_expr=f"[{value.x}]", _var_type=Coordinate)

        assert str(LiteralVar.create(Coordinate(2))) == "[2]"
    finally:
        serializers.SERIALIZERS.pop(Coordinate)
        serializers.SERIALIZER_TYPES.pop(Coordinate)
        serializers.get_serializer.cache_clear()
        serializers.get_serializer_type.cache_clear()
        del base._var_subclasses[var_subclasses:]
        del base._var_literal_subclasses[literal_subclasses:]
        base._clear_var_subclass_lookup_caches()
        base._literal_var_by_type.clear()


def test_guess_type_dispatch_follows_later_registrations():
    """A Var subclass registered after a guess wins the next guess for its type."""

    class Tags(list):
        """A list type no Var subclass claims yet."""

    from reflex_base.vars import base

    var_subclasses = len(base._var_subclasses)
    tags = Var(_js_expr="tags", _var_type=Tags)
    try:
        assert isinstance(tags.guess_type(), ArrayVar)
        assert isinstance(tags.guess_type(), ArrayVar)

        class TagsVar(ArrayVar, python_types=Tags):
            """A Var holding tags."""

        assert isinstance(tags.guess_type(), TagsVar)
    finally:
        del base._var_subclasses[var_subclasses:]
        base._clear_var_subclass_lookup_caches()


def test_guess_type_with_an_unhashable_var_type():
    """A var type that cannot be a cache key is still guessed."""
    var = Var(_js_expr="x", _var_type=typing.Annotated[int, []])
    assert isinstance(var.guess_type(), NumberVar)
    assert isinstance(var.guess_type(), NumberVar)


def test_cached_property_releases_entries_across_a_hierarchy():
    """Every cached property of a class and its bases is released with the instance."""

    class Base:
        @cached_property
        def first(self) -> list[int]:
            return [1]

    class Child(Base):
        @cached_property
        def second(self) -> list[int]:
            return [2]

        @cached_property
        def never_read(self) -> list[int]:
            return [3]

    child = Child()
    assert child.first == [1]
    assert child.second == [2]
    keys = [
        child.__dict__["_reflex_cache_first"],
        child.__dict__["_reflex_cache_second"],
    ]
    assert all(key in GLOBAL_CACHE for key in keys)
    del child
    gc.collect()
    assert not any(key in GLOBAL_CACHE for key in keys)


def test_cached_property_keeps_running_an_inherited_del():
    """A __del__ the owner inherits still runs after its cached entries are released."""
    deleted = []

    class Base:
        def __del__(self):
            deleted.append(type(self).__name__)

    class Child(Base):
        @cached_property
        def value(self) -> list[int]:
            return [1]

    child = Child()
    assert child.value == [1]
    key = child.__dict__["_reflex_cache_value"]
    del child
    gc.collect()
    assert deleted == ["Child"]
    assert key not in GLOBAL_CACHE


def _operand_with_var_data() -> NumberVar[int]:
    """Build an operand carrying imports and hooks worth losing.

    Returns:
        A number Var whose VarData has to survive into any operation built from it.
    """
    return Var(
        _js_expr="operandValue",
        _var_data=VarData(
            imports={"operand-lib": [ImportVar(tag="operandThing")]},
            hooks={"const operand = useOperand()": None},
        ),
    ).to(int)


@pytest.mark.parametrize(
    ("build", "expected_js"),
    [
        pytest.param(lambda v: v + 1, "(operandValue + 1)", id="add"),
        pytest.param(lambda v: v - 1, "(operandValue - 1)", id="subtract"),
        pytest.param(lambda v: v > 1, "(operandValue > 1)", id="greater_than"),
        pytest.param(
            lambda v: v.bool() & v.bool(),
            "pyAnd(isTrue(operandValue), () => (isTrue(operandValue)))",
            id="logical_and",
        ),
        pytest.param(lambda v: v.to_string().lower(), None, id="string_lower"),
        pytest.param(lambda v: v.to(ArrayVar).length(), None, id="array_length"),
        pytest.param(lambda v: v.to(ObjectVar).keys(), None, id="object_keys"),
        pytest.param(lambda v: (v + 1) * 2 > 3, None, id="chained"),
    ],
)
def test_var_operation_operands_do_not_register_global_vars(
    build: typing.Callable[[NumberVar[int]], Var], expected_js: str | None
) -> None:
    """Building an operation leaves the module-global var registry alone.

    Operation bodies interpolate their operands with ``!s``, which renders the
    expression directly. Interpolating them with ``{}`` instead would hash each
    operand, register it in ``_global_vars`` forever — a leak that grows with
    every operation an app builds — and emit a tag the result then has to
    regex-decode back out, all to recover VarData that ``_args`` already
    carries.

    Args:
        build: Builds the operation from an operand.
        expected_js: The expected JavaScript, when it is short enough to pin.
    """
    operand = _operand_with_var_data()

    before = len(_global_vars)
    result = build(operand)
    assert len(_global_vars) == before

    if expected_js is not None:
        assert str(result) == expected_js


def test_var_operation_rolls_up_operand_var_data() -> None:
    """An operand's imports and hooks still reach the operation it is used in.

    They arrive through ``CustomVarOperation._args`` rather than through a tag
    decoded out of the returned expression, which is what makes ``!s`` safe.
    """
    operand = _operand_with_var_data()

    var_data = (operand + 1)._get_all_var_data()

    assert var_data is not None
    assert dict(var_data.imports)["operand-lib"] == (ImportVar(tag="operandThing"),)
    assert "const operand = useOperand()" in var_data.hooks


def test_var_operation_body_created_var_still_tags() -> None:
    """A var built inside a body is not an operand and must keep its tag.

    ``_args`` only carries what was passed in, so a var the body creates itself
    reaches the operation solely through the returned expression. It therefore
    interpolates with ``{}``, and ``!s`` would silently drop its imports.
    """

    @var_operation
    def op_with_derived(value: Var):
        derived = Var(
            _js_expr="derivedHelper",
            _var_data=VarData(imports={"derived-lib": [ImportVar(tag="helper")]}),
        )
        return var_operation_return(f"({value!s} + {derived})", var_type=int)

    result = op_with_derived(Var(_js_expr="a").to(int))

    var_data = result._get_all_var_data()
    assert var_data is not None
    assert dict(var_data.imports)["derived-lib"] == (ImportVar(tag="helper"),)
    assert str(result) == "(a + derivedHelper)"


# Decorators whose function body builds a var operation's expression out of the
# function's own parameters. ``var_operation`` wraps every argument with
# ``LiteralVar.create``, so inside these bodies every parameter is a Var.
_OPERAND_BUILDER_DECORATORS = frozenset({
    "var_operation",
    "binary_number_operation",
    "comparison_operator",
})
# Plain helpers called only from such a body, mapped to the parameters the
# operation forwards its operands into. Their other parameters are ordinary
# Python values that never carried a tag to begin with.
_OPERAND_BUILDER_FUNCTIONS = {"date_compare_operation": frozenset({"lhs", "rhs"})}


def test_var_operation_bodies_interpolate_operands_with_str() -> None:
    """No operation body interpolates an operand without ``!s``.

    The rule is checked against the source rather than per operation, because
    a missed one changes no behaviour: the rendered JavaScript and the merged
    VarData come out identical, and only the leak and the cost give it away.
    A var the body creates itself is not a parameter, so it is not flagged.
    """
    import ast
    import pathlib

    from reflex_base.vars import base as base_module

    offenders: list[str] = []
    for path in sorted(pathlib.Path(base_module.__file__).parent.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = {d.id for d in node.decorator_list if isinstance(d, ast.Name)}
            if decorators & _OPERAND_BUILDER_DECORATORS:
                params = {arg.arg for arg in node.args.args}
            elif node.name in _OPERAND_BUILDER_FUNCTIONS:
                params = _OPERAND_BUILDER_FUNCTIONS[node.name]
            else:
                continue
            for joined in ast.walk(node):
                if not isinstance(joined, ast.JoinedStr):
                    continue
                for value in joined.values:
                    if (
                        isinstance(value, ast.FormattedValue)
                        and isinstance(value.value, ast.Name)
                        and value.value.id in params
                        and value.conversion != ord("s")
                    ):
                        offenders.append(
                            f"{path.name}:{value.lineno} {node.name} "
                            f"interpolates operand {value.value.id!r} without !s"
                        )

    assert not offenders, (
        "Var operation bodies must interpolate their operands with !s, which "
        "renders the expression directly; plain {} hashes the operand and "
        "registers it in _global_vars forever to recover VarData that _args "
        "already carries:\n  " + "\n  ".join(offenders)
    )


def test_var_operation_str_interpolation_matches_tagged_form() -> None:
    """``!s`` renders exactly what a tagged interpolation decodes down to.

    ``Var.__format__`` emits a tag followed by the expression, and the Var it
    is interpolated into strips the tag back off in ``__post_init__``. ``!s``
    just skips the round trip, so the two have to agree.
    """
    operand = _operand_with_var_data()

    tagged = Var(_js_expr=f"wrap({operand})").to(int)
    untagged = Var(_js_expr=f"wrap({operand!s})").to(int)

    assert str(tagged) == str(untagged) == "wrap(operandValue)"


@pytest.mark.parametrize(
    "name",
    [
        "_init_bookkeeping",
        "_get_root_state",
        "_was_touched",
        "dirty_vars",
        "get_fields",
        "get_full_name",
        "computed_vars",
        "__fields__",
        "setvar",
    ],
)
@pytest.mark.parametrize("annotated", [False, True])
def test_reserved_state_var(name: str, annotated: bool, clean_registration_context):
    """Reject framework names before state initialization can call them.

    Args:
        name: The reserved member to shadow.
        annotated: Whether to explicitly annotate the variable.
        clean_registration_context: An isolated state registry.
    """
    namespace = {"__module__": __name__, "__qualname__": "ShadowState", name: 7}
    if annotated:
        namespace["__annotations__"] = {name: int}
    with pytest.raises(StateValueError, match=name):
        type("ShadowState", (BaseState,), namespace)


def test_reserved_annotation_only(clean_registration_context):
    """Reject a reserved var even when no default is declared.

    Args:
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="_init_bookkeeping"):

        class ShadowState(BaseState):
            _init_bookkeeping: int


@pytest.mark.parametrize("state_mixin", [False, True])
def test_reserved_mixin_var(state_mixin: bool, clean_registration_context):
    """Reject collisions from both ordinary Python mixins and state mixins.

    Args:
        state_mixin: Whether the mixin subclasses BaseState.
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="_get_root_state"):
        mixin = type(
            "Mixin",
            (BaseState,) if state_mixin else (),
            {"__module__": __name__, "_get_root_state": 7},
            **({"mixin": True} if state_mixin else {}),
        )
        type("MixedState", (mixin, BaseState), {"__module__": __name__})


@pytest.mark.parametrize("state_mixin", [False, True])
def test_abc_mixin(state_mixin: bool, clean_registration_context):
    """Accept an ``ABC`` mixin, whose ``_abc_impl`` the metaclass owns, and keep it abstract.

    Args:
        state_mixin: Whether the abstract mixin subclasses BaseState.
        clean_registration_context: An isolated state registry.
    """

    class Abstract(ABC):
        @abstractmethod
        def _value(self) -> int: ...

    if state_mixin:

        class Mixin(Abstract, BaseState, mixin=True):
            pass

        bases = (Mixin, BaseState)
    else:
        bases = (Abstract, BaseState)

    abstract_state = type("AbstractState", bases, {"__module__": __name__})
    with pytest.raises(TypeError, match="_value"):
        abstract_state()

    concrete_state = type(
        "ConcreteState", bases, {"__module__": __name__, "_value": lambda self: 7}
    )
    assert concrete_state()._value() == 7


@pytest.mark.parametrize("registration", ["declared", "var"])
def test_reserved_abc_bookkeeping(registration: str, clean_registration_context):
    """Keep rejecting a state's own ``_abc_impl``, which would clash with ABCMeta's.

    Args:
        registration: Whether the name is declared in the class body or added later.
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match=_ABC_BOOKKEEPING_NAME):
        if registration == "declared":

            class ShadowState(ABC, BaseState):
                _abc_impl: int = 7

        else:

            class DynamicState(ABC, BaseState):
                """State receiving a dynamic declaration."""

            DynamicState.add_var(_ABC_BOOKKEEPING_NAME, int, 7)


@pytest.mark.parametrize("slots", [("cache",), "cache"])
@pytest.mark.parametrize("state_base", [False, True])
def test_reserved_slot_of_base(
    state_base: bool, slots: tuple[str, ...] | str, clean_registration_context
):
    """Reject a declaration using a slot name of a non-root base, and only those.

    Args:
        state_base: Whether the slotted base is a state or a Python mixin.
        slots: The base's ``__slots__``; a single string declares one slot.
        clean_registration_context: An isolated state registry.
    """
    slotted = type(
        "Slotted",
        (BaseState,) if state_base else (),
        {"__module__": __name__, "__slots__": slots},
    )
    bases = (slotted,) if state_base else (slotted, BaseState)
    with pytest.raises(StateValueError, match=r"\['cache'\] are reserved by Slotted"):
        type(
            "SlotShadowState",
            bases,
            {"__module__": __name__, "__annotations__": {"cache": int}, "cache": 0},
        )
    if state_base:
        # A name that is only a substring of the slot name is not reserved; a
        # slotted Python mixin cannot be combined with a state at all.
        state = type(
            "SubstringState",
            bases,
            {"__module__": __name__, "__annotations__": {"c": int}, "c": 0},
        )
        assert "c" in state.get_fields()


@pytest.mark.parametrize("name", ["_init_bookkeeping", "get_fields"])
def test_reserved_computed_var(name: str, clean_registration_context):
    """Reject computed vars that replace framework methods.

    Args:
        name: The reserved method to replace.
        clean_registration_context: An isolated state registry.
    """

    def value(self) -> int:
        """Return a constant computed value."""
        return 7

    value.__name__ = name
    with pytest.raises(StateValueError, match=name):
        type(
            "ComputedState",
            (BaseState,),
            {"__module__": __name__, name: computed_var(value)},
        )


@pytest.mark.parametrize("registration", ["var", "route", "event", "field"])
def test_dynamic_reserved_name(registration: str, clean_registration_context):
    """Reject dynamic collisions before any field or event map is changed.

    Args:
        registration: The dynamic registration path to exercise.
        clean_registration_context: An isolated state registry.
    """

    class DynamicState(BaseState):
        """State receiving a dynamic declaration."""

    fields = dict(DynamicState.get_fields())
    with pytest.raises(StateValueError, match="get_state"):
        if registration == "var":
            DynamicState.add_var("get_state", int, 7)
        elif registration == "route":
            DynamicState.setup_dynamic_args({"get_state": RouteArgType.SINGLE})
        elif registration == "event":
            DynamicState._add_event_handler("get_state", lambda self: None)
        else:
            DynamicState.add_field("get_state", LiteralVar.create(7), 7)
    assert DynamicState.get_fields() == fields
    assert "get_state" not in DynamicState.vars
    assert "get_state" not in DynamicState.event_handlers
    assert "get_state" not in DynamicState.__dict__


def test_user_vars_and_marked_override(clean_registration_context):
    """Keep normal vars, inherited vars, and explicitly marked method overrides.

    Args:
        clean_registration_context: An isolated state registry.
    """

    class Parent(BaseState):
        value: int = 1
        _backend: int = 2

    class Child(Parent):
        @_override_base_method
        def get_value(self, key: str):
            """Return a value through a supported framework override."""
            return f"override:{key}"

    parent = Parent()
    child = parent.substates[Child.get_name()]
    assert isinstance(child, Child)
    assert child.value == 1
    assert child._backend == 2
    assert child.get_value("value") == "override:value"


def test_non_state_models_keep_their_namespace():
    """Do not reserve Reflex state names on unrelated base models."""

    class Model(EvenMoreBasicBaseState):
        get_state: int = 7

    assert Model().get_state == 7


@pytest.mark.parametrize("name", ["get_fields", "_init_bookkeeping"])
@pytest.mark.parametrize("state_first", [False, True])
def test_reserved_model_mixin(name: str, state_first: bool, clean_registration_context):
    """Reject inherited model fields before the field collector sees them.

    Args:
        name: The framework name declared as a model field.
        state_first: Whether BaseState precedes the model in the MRO.
        clean_registration_context: An isolated state registry.
    """
    model = type("Model", (EvenMoreBasicBaseState,), {"__module__": __name__, name: 7})
    bases = (BaseState, model) if state_first else (model, BaseState)
    with pytest.raises(StateValueError, match=name):
        type("MixedState", bases, {"__module__": __name__})


def test_reserved_descriptor(clean_registration_context):
    """Reject a descriptor without executing its class access behavior.

    Args:
        clean_registration_context: An isolated state registry.
    """

    class Descriptor:
        def __get__(self, instance, owner):
            """Fail if validation invokes this descriptor."""
            pytest.fail("Reserved descriptor was evaluated")

    with pytest.raises(StateValueError, match="get_fields"):
        type(
            "DescriptorState",
            (BaseState,),
            {"__module__": __name__, "get_fields": Descriptor()},
        )


class _CookieMeta(BaseStateMeta):
    """A downstream-style metaclass that injects fields into the declaration."""

    def __new__(
        cls, name: str, bases: tuple[type, ...], namespace: dict[str, Any], **kwargs
    ):
        """Add an annotated backend var before the state is constructed.

        Args:
            name: The class name.
            bases: The parent classes.
            namespace: The class namespace.
            **kwargs: Class creation keywords, e.g. `mixin`.

        Returns:
            The new state class.
        """
        namespace.setdefault("__annotations__", {})["_injected"] = str
        namespace["_injected"] = "by the metaclass"
        return super().__new__(cls, name, bases, namespace, **kwargs)


def test_state_metaclass_is_base_state_meta():
    """Keep the exported `BaseStateMeta` as the metaclass of every state."""
    assert type(BaseState) is BaseStateMeta
    assert type(State) is BaseStateMeta
    assert BaseState._reflex_state_root is BaseState
    assert State._reflex_state_root is BaseState


@pytest.mark.parametrize("mixin", [False, True])
def test_custom_state_metaclass(mixin: bool, clean_registration_context):
    """Allow a `BaseStateMeta` subclass as the metaclass of a state.

    Args:
        mixin: Whether the state is declared as a state mixin.
        clean_registration_context: An isolated state registry.
    """

    class CustomState(State, mixin=mixin, metaclass=_CookieMeta):
        value: int = 1

    assert type(CustomState) is _CookieMeta
    assert CustomState._mixin is mixin
    assert CustomState.__fields__["_injected"].default == "by the metaclass"
    assert CustomState.__fields__["value"].default == 1


def test_custom_state_metaclass_validates_reserved_names(clean_registration_context):
    """Keep rejecting reserved names declared through a custom metaclass.

    Args:
        clean_registration_context: An isolated state registry.
    """
    with pytest.raises(StateValueError, match="get_fields"):

        class ShadowState(BaseState, metaclass=_CookieMeta):
            get_fields: int = 7


def test_state_root_reserves_its_own_namespace():
    """Reserve the members of a `state_root=True` class for its whole hierarchy."""

    class Root(EvenMoreBasicBaseState, state_root=True):
        def bookkeeping(self) -> int:
            """Return a framework-style member subclasses may not shadow."""
            return 1

    class Child(Root):
        value: int = 5

    assert Child._reflex_state_root is Root
    assert Child().value == 5
    with pytest.raises(StateValueError, match="bookkeeping"):

        class ShadowMethod(Root):
            bookkeeping: int = 7

    with pytest.raises(StateValueError, match="_reflex_state_root"):
        type("ShadowMarker", (Root,), {"__module__": __name__, "_reflex_state_root": 7})


def test_state_roots_do_not_share_reserved_names():
    """Keep one root's reserved namespace out of another root's hierarchy."""

    class RootA(EvenMoreBasicBaseState, state_root=True):
        def alpha(self) -> int:
            """Return a member reserved for RootA's subclasses only."""
            return 1

    class RootB(EvenMoreBasicBaseState, state_root=True):
        def beta(self) -> int:
            """Return a member reserved for RootB's subclasses only."""
            return 2

    class A(RootA):
        beta: int = 1

    class B(RootB):
        alpha: int = 2

    assert (A().beta, B().alpha) == (1, 2)
    assert A._reflex_state_root is RootA
    assert B._reflex_state_root is RootB
    with pytest.raises(StateValueError, match="alpha"):

        class ShadowA(RootA):
            alpha: int = 3


def test_inherited_field_on_plain_model():
    """An inherited field of a model without a state tree reads from the model itself."""

    class Model(EvenMoreBasicBaseState):
        x: int = 1

    class SubModel(Model):
        pass

    model = SubModel()
    assert model.x == 1
    model.x = 2
    assert model.x == 2


def test_new_default_for_inherited_field_declares_a_field():
    """Assigning a default to an inherited field redeclares it with that default."""

    class Parent(State):
        count: int = 0

    class Child(Parent):
        count = 5

    child_field = Child.get_fields()["count"]
    assert child_field is not Parent.get_fields()["count"]
    assert child_field.default == 5
    assert child_field.outer_type_ is int
    assert "count" in Child.base_vars


class TaggedField(Field[FIELD_TYPE]):
    """A field subclass with an attribute of its own."""

    def __init__(self, *args: Any, tag: str = "", **kwargs: Any):
        """Initialize the field.

        Args:
            *args: The arguments of Field.
            tag: The tag of the field.
            **kwargs: The keyword arguments of Field.
        """
        super().__init__(*args, **kwargs)
        self.tag = tag

    def _replace(self, **kwargs: Any) -> Self:
        """Derive a field, keeping the tag.

        Args:
            **kwargs: The arguments to replace.

        Returns:
            The new field.
        """
        return super()._replace(**{"tag": self.tag, **kwargs})


def test_field_subclass_is_kept():
    """A field declared with a Field subclass stays one wherever it is copied."""

    class Parent(State):
        annotated: int = TaggedField(default=1, tag="a")  # pyright: ignore[reportAssignmentType]
        generic: TaggedField[int] = TaggedField(default=2, tag="g")
        unannotated = TaggedField(default="x", tag="u")

    class Child(Parent):
        annotated = 3

    class AnnotatedChild(Parent):
        annotated: int = 5

    class Mixin(State, mixin=True):
        mixed: int = TaggedField(default=4, tag="m")  # pyright: ignore[reportAssignmentType]

    class UsesMixin(Mixin, State):
        pass

    for cls, name, tag, default in (
        (Parent, "annotated", "a", 1),
        (Parent, "generic", "g", 2),
        (Parent, "unannotated", "u", "x"),
        (Child, "annotated", "a", 3),
        (AnnotatedChild, "annotated", "a", 5),
        (UsesMixin, "mixed", "m", 4),
    ):
        declared = cls.get_fields()[name]
        assert type(declared) is TaggedField, (cls, name)
        assert declared.tag == tag
        assert declared.default_value() == default
    assert Parent.get_fields()["generic"].outer_type_ is int
    assert UsesMixin.get_fields()["mixed"] is not Mixin.get_fields()["mixed"]


def test_plain_model_without_reflex():
    """A plain model's fields work in a process that never imports reflex."""
    code = """
import sys
from reflex_base.vars import EvenMoreBasicBaseState

class Model(EvenMoreBasicBaseState):
    count: int = 0

model = Model(count=3)
model.count = 4
assert model.count == 4
assert "reflex" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_plain_model_unwraps_state_proxies():
    """A plain model stores the value of a state's mutable var, not its proxy."""

    class Items(State):
        items: list[int] = [1]

    class Model(EvenMoreBasicBaseState):
        items: list[int] = []

    model = Model()
    model.items = Items().items
    assert type(vars(model)["items"]) is list


def test_slot_names_are_reserved():
    """A state cannot declare a name a base keeps in a slot."""

    class Root(EvenMoreBasicBaseState, state_root=True):
        pass

    class Base(Root):
        __slots__ = ("_bookkeeping",)

    with pytest.raises(StateValueError, match="_bookkeeping"):

        class Shadow(Base):
            _bookkeeping: int = 0


def test_backend_field_is_not_type_checked():
    """Setting a backend var skips the type check, like a generic one it cannot run."""
    T = TypeVar("T")

    class Model(EvenMoreBasicBaseState):
        _value: T  # pyright: ignore[reportGeneralTypeIssues]

    model = Model()  # pyright: ignore[reportCallIssue]
    model._value = 1
    assert model._value == 1


@pytest.mark.parametrize("name", ["_secret", "bookkeeping"])
def test_backend_field_format_raises(name: str):
    """Formatting a backend var raises instead of embedding its repr.

    Args:
        name: The backend field to format, underscore-prefixed or is_var=False.
    """

    class Model(EvenMoreBasicBaseState):
        _secret: int = 42
        bookkeeping: int = field(default=0, is_var=False)

    with pytest.raises(
        BackendVarFormatError, match=rf"Backend var 'Model\.{name}' exists only"
    ):
        f"{getattr(Model, name)}px"


@pytest.mark.parametrize(("name", "default"), [("_secret", 42), ("bookkeeping", 0)])
def test_backend_field_format_error_names_the_fix(name: str, default: int):
    """The backend var format error names the var and how to use it in the UI.

    Args:
        name: The backend field to format, underscore-prefixed or is_var=False.
        default: The default value of that field.
    """

    class Model(EvenMoreBasicBaseState):
        _secret: int = 42
        bookkeeping: int = field(default=0, is_var=False)

    with pytest.raises(BackendVarFormatError) as exc_info:
        f"{getattr(Model, name)}px"

    message = str(exc_info.value)
    assert f"Backend var 'Model.{name}' exists only on the server" in message
    assert f"Use Model.{name}.default_value() for its default value" in message
    assert "declare it as ClassVar[...]" in message
    assert "use a regular state var" in message
    # The suggested call returns the default.
    assert getattr(Model, name).default_value() == default


def test_mixin_field_format_raises():
    """A mixin's frontend field has no Var, and the error says to use the including state."""

    class Mixin(EvenMoreBasicBaseState, mixin=True):
        count: int = 0

    with pytest.raises(
        BackendVarFormatError, match=r"Var 'Mixin\.count' is declared on a mixin state"
    ):
        f"{Mixin.count}"


def test_unbound_field_format_raises():
    """An unbound field has no Var to format, and the error shows its definition."""
    with pytest.raises(
        BackendVarFormatError,
        match=r"^Field\(default=0, is_var=True, annotated_type=typing.Any\) has no",
    ):
        f"{field(default=0)}"


def test_untyped_var_item_access_reports_backend_var_key():
    """Indexing an untyped Var with a backend var names the key, not a format error."""

    class Model(EvenMoreBasicBaseState):
        _secret: int = 42

    with pytest.raises(UntypedVarError, match=r"access the item 'Field\(default=42"):
        Var(_js_expr="x")[Model._secret]  # pyright: ignore[reportIndexIssue]


def test_backend_field_literal_var_reports_repr():
    """Creating a LiteralVar from a backend var reports its repr, not a format error."""

    class Model(EvenMoreBasicBaseState):
        _secret: int = 42

    with pytest.raises(
        TypeError, match=r"Tried to create a LiteralVar from Field\(default=42"
    ):
        LiteralVar.create(Model._secret)


def test_mistyped_backend_field_value_logs_repr(caplog: pytest.LogCaptureFixture):
    """Assigning a backend var to a typed field logs its repr and stores it.

    Args:
        caplog: The log capture fixture.
    """

    class Model(EvenMoreBasicBaseState):
        _secret: int = 42
        count: int = 0

    model = Model()  # pyright: ignore[reportCallIssue]
    with caplog.at_level(logging.ERROR, logger="reflex_base.vars.base"):
        model.count = Model._secret  # pyright: ignore[reportAttributeAccessIssue]
    assert "but got Field(default=42" in caplog.text
    assert model.__dict__["count"] is Model._secret


def test_classvar_over_inherited_field_is_not_a_field():
    """A ClassVar redeclaring an inherited field stays a class attribute."""

    class Parent(State):
        count: int = 0

    class Child(Parent):
        count: ClassVar[int] = 5  # pyright: ignore[reportIncompatibleVariableOverride]

    assert Child.get_fields()["count"] is Parent.get_fields()["count"]
    assert "count" not in Child.base_vars


def test_computed_var_type_mismatch_is_logged_once_per_value(
    caplog: pytest.LogCaptureFixture,
):
    """A computed value of the wrong type is reported when computed, not on each read.

    Args:
        caplog: The log capture fixture.
    """

    class MismatchState(BaseState):
        count: int = 0

        @computed_var
        def cached(self) -> int:
            return str(self.count)  # pyright: ignore [reportReturnType]

        @computed_var(cache=False)
        def uncached(self) -> int:
            return str(self.count)  # pyright: ignore [reportReturnType]

    state = MismatchState()
    with caplog.at_level(logging.ERROR, logger="reflex_base.vars.base"):
        assert [state.cached for _ in range(3)] == ["0"] * 3
        assert len(caplog.records) == 1
        assert "MismatchState.cached" in caplog.text
        state.count = 1
        assert state.cached == "1"
        assert len(caplog.records) == 2
        caplog.clear()
        assert [state.uncached for _ in range(3)] == ["1"] * 3
        assert len(caplog.records) == 3


async def test_async_computed_var_type_mismatch_is_logged_once_per_value(
    caplog: pytest.LogCaptureFixture,
):
    """An async computed value of the wrong type is reported when computed, not on each read.

    Args:
        caplog: The log capture fixture.
    """

    class AsyncMismatchState(BaseState):
        count: int = 0

        @computed_var
        async def cached(self) -> int:
            return str(self.count)  # pyright: ignore [reportReturnType]

        @computed_var(cache=False)
        async def uncached(self) -> int:
            return str(self.count)  # pyright: ignore [reportReturnType]

    state = AsyncMismatchState()
    with caplog.at_level(logging.ERROR, logger="reflex_base.vars.base"):
        for _ in range(3):
            assert await state.cached == "0"  # pyright: ignore [reportGeneralTypeIssues]
        assert len(caplog.records) == 1
        state.count = 1
        assert await state.cached == "1"  # pyright: ignore [reportGeneralTypeIssues]
        assert len(caplog.records) == 2
        caplog.clear()
        for _ in range(3):
            assert await state.uncached == "1"  # pyright: ignore [reportGeneralTypeIssues]
        assert len(caplog.records) == 3


@pytest.mark.parametrize(
    ("annotation", "value", "mismatch"),
    [
        (int, 1, False),
        (int, "1", True),
        (bool, 1, True),
        (float, 1, False),
        (float, "1", True),
        (int | None, None, False),
        (int | None, "1", True),
        (list[int], [1], False),
        (list[int], ["1"], True),
        (dict[str, int], {"a": 1}, False),
        (dict[str, int], {"a": "1"}, True),
    ],
)
def test_computed_var_return_type_check(
    annotation: Any,
    value: Any,
    mismatch: bool,
    caplog: pytest.LogCaptureFixture,
    clean_registration_context,
):
    """A computed value is checked against the return type, plain classes included.

    Args:
        annotation: The return type of the computed var.
        value: The value it computes.
        mismatch: Whether the value does not match the return type.
        caplog: The log capture fixture.
        clean_registration_context: An isolated state registry.
    """

    def compute(self):
        return value

    state_cls = type(
        "ReturnTypeState",
        (BaseState,),
        {
            "__module__": __name__,
            "compute": computed_var(compute, return_type=annotation, auto_deps=False),
        },
    )
    state = state_cls()
    with caplog.at_level(logging.ERROR, logger="reflex_base.vars.base"):
        assert state.compute == value  # pyright: ignore [reportAttributeAccessIssue]
    assert bool(caplog.records) is mismatch


def test_computed_var_update_time_is_only_kept_for_interval_vars():
    """Only a computed var with an update interval stores when it was last computed."""
    calls = 0

    class TimedState(BaseState):
        count: int = 0

        @computed_var
        def plain(self) -> int:
            return self.count

        @computed_var(interval=datetime.timedelta(seconds=30))
        def timed(self) -> int:
            nonlocal calls
            calls += 1
            return self.count

    state = TimedState()
    plain, timed = TimedState.computed_vars["plain"], TimedState.computed_vars["timed"]
    assert (state.plain, state.timed) == (0, 0)
    assert plain._last_updated_attr not in vars(state)
    assert timed._last_updated_attr in vars(state)
    assert not plain.needs_update(state)
    assert not timed.needs_update(state)

    # The cached value is served until the interval has elapsed.
    assert (state.timed, calls) == (0, 1)
    vars(state)[timed._last_updated_attr] -= datetime.timedelta(seconds=31)
    assert timed.needs_update(state)
    assert (state.timed, calls) == (0, 2)
    assert not timed.needs_update(state)


def test_computed_var_mark_dirty_drops_only_the_cached_value():
    """Marking a computed var dirty drops its cached value, whether there is one or not."""

    class DirtyState(BaseState):
        count: int = 1

        @computed_var
        def doubled(self) -> int:
            return self.count * 2

    state = DirtyState()
    doubled = DirtyState.computed_vars["doubled"]
    doubled.mark_dirty(state)
    assert doubled._cache_attr not in vars(state)
    assert state.doubled == 2
    assert vars(state)[doubled._cache_attr] == 2
    doubled.mark_dirty(state)
    doubled.mark_dirty(state)
    assert doubled._cache_attr not in vars(state)
    assert state.doubled == 2


def test_computed_var_caches_a_missing_value():
    """A computed var returning `dataclasses.MISSING` is cached like any other value."""
    calls = 0

    class MissingValueState(BaseState):
        @computed_var
        def missing(self) -> object:
            nonlocal calls
            calls += 1
            return dataclasses.MISSING

    state = MissingValueState()
    assert state.missing is dataclasses.MISSING
    state._was_touched = False
    assert state.missing is dataclasses.MISSING
    assert calls == 1
    assert not state._was_touched


async def test_async_computed_var_caches_a_missing_value():
    """An async computed var returning `dataclasses.MISSING` is cached like any other value."""
    calls = 0

    class AsyncMissingValueState(BaseState):
        @computed_var
        async def missing(self) -> object:
            nonlocal calls
            calls += 1
            return dataclasses.MISSING

    state = AsyncMissingValueState()
    assert await state.missing is dataclasses.MISSING  # pyright: ignore [reportGeneralTypeIssues]
    state._was_touched = False
    assert await state.missing is dataclasses.MISSING  # pyright: ignore [reportGeneralTypeIssues]
    assert calls == 1
    assert not state._was_touched


class _Flavor(enum.IntEnum):
    SWEET = 1


class _Label(str):
    pass


class _Items(list):
    pass


@dataclasses.dataclass
class _Point:
    x: int = 0


@pytest.mark.parametrize(
    ("annotation", "value"),
    [
        (int, 1),
        (str, "a"),
        (float, 1.5),
        (bool, True),
        (int | None, None),
        (_Flavor, _Flavor.SWEET),
        (_Label, _Label("a")),
    ],
    ids=repr,
)
def test_field_read_leaves_immutable_values_unwrapped(annotation: Any, value: Any):
    """A field holding an immutable value reads back that very value.

    Args:
        annotation: The type of the field.
        value: The value to store.
    """
    state_cls = type(
        "ImmutableReadState",
        (BaseState,),
        {
            "__module__": __name__,
            "__annotations__": {"item": annotation},
            "item": value,
        },
    )
    state = state_cls()
    state.item = value  # pyright: ignore [reportAttributeAccessIssue]
    assert state.item is value  # pyright: ignore [reportAttributeAccessIssue]


@pytest.mark.parametrize(
    ("annotation", "value"),
    [
        (list[int], [1]),
        (dict[str, int], {"a": 1}),
        (set[int], {1}),
        (_Items, _Items([1])),
        (_Point, _Point(1)),
    ],
    ids=repr,
)
def test_field_read_wraps_mutable_values(annotation: Any, value: Any):
    """A field holding a mutable value reads back a proxy of it.

    Args:
        annotation: The type of the field.
        value: The value to store.
    """
    state_cls = type(
        "MutableReadState",
        (BaseState,),
        {"__module__": __name__, "__annotations__": {"item": annotation}},
    )
    state = state_cls()
    state.item = value  # pyright: ignore [reportAttributeAccessIssue]
    assert isinstance(state.item, MutableProxy)  # pyright: ignore [reportAttributeAccessIssue]
    assert state.item.__wrapped__ is value  # pyright: ignore [reportAttributeAccessIssue]


def test_cached_computed_var_checks_return_type_on_recompute_only(
    monkeypatch: pytest.MonkeyPatch,
):
    """A cached computed var validates its return type only when it recomputes."""

    class CheckedState(BaseState):
        items: list[int] = [1, 2, 3]

        @computed_var
        def doubled(self) -> list[int]:
            return [i * 2 for i in self.items]

    checked = []
    original = CheckedState.computed_vars["doubled"]._check_deprecated_return_type
    monkeypatch.setattr(
        type(CheckedState.computed_vars["doubled"]),
        "_check_deprecated_return_type",
        lambda self, instance, value: (
            checked.append(value) or original(instance, value)
        ),
    )
    state = CheckedState()

    assert state.doubled == [2, 4, 6]
    assert state.doubled == [2, 4, 6]
    assert checked == [[2, 4, 6]]

    state.items = [5]
    assert state.doubled == [10]
    assert checked == [[2, 4, 6], [10]]


@pytest.fixture
def restore_env_mode() -> Iterator[None]:
    """Restore REFLEX_ENV_MODE and the cached type check depth after a test.

    Yields:
        None.
    """
    original = os.environ.get(environment.REFLEX_ENV_MODE.name)
    yield
    if original is None:
        os.environ.pop(environment.REFLEX_ENV_MODE.name, None)
    else:
        os.environ[environment.REFLEX_ENV_MODE.name] = original
    _type_check_depth.cache_clear()


@pytest.mark.usefixtures("restore_env_mode")
def test_type_check_depth_follows_env_mode_set():
    """Setting REFLEX_ENV_MODE re-resolves the cached type check depth."""
    environment.REFLEX_ENV_MODE.set(constants.Env.DEV)
    assert _type_check_depth() == 1
    environment.REFLEX_ENV_MODE.set(constants.Env.PROD)
    assert _type_check_depth() == 0
    environment.REFLEX_ENV_MODE.set(None)
    assert _type_check_depth() == 1


@pytest.mark.usefixtures("restore_env_mode")
def test_type_check_depth_follows_env_mode_from_env_file(tmp_path: Path):
    """Loading an env file that sets REFLEX_ENV_MODE re-resolves the depth.

    Args:
        tmp_path: Pytest temporary directory.
    """
    environment.REFLEX_ENV_MODE.set(constants.Env.DEV)
    assert _type_check_depth() == 1
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"{environment.REFLEX_ENV_MODE.name}={constants.Env.PROD.value}\n"
    )
    _load_dotenv_from_files([env_file])
    assert _type_check_depth() == 0


@pytest.mark.usefixtures("restore_env_mode")
@pytest.mark.parametrize(
    ("env_mode", "element_error_logged"),
    [(constants.Env.DEV, True), (constants.Env.PROD, False)],
)
def test_state_var_type_check_depth_follows_env_mode(
    caplog: pytest.LogCaptureFixture,
    env_mode: constants.Env,
    element_error_logged: bool,
):
    """Prod mode checks only the outer type of assigned and computed values.

    Args:
        caplog: Pytest log capture fixture.
        env_mode: The REFLEX_ENV_MODE value.
        element_error_logged: Whether a wrong element type is reported.
    """

    class DepthState(BaseState):
        items: list[int] = []
        wrong_elements: list[str] = []

        @computed_var
        def as_ints(self) -> list[int]:
            return self.wrong_elements  # pyright: ignore[reportReturnType]

    environment.REFLEX_ENV_MODE.set(env_mode)
    state = DepthState()

    with caplog.at_level(logging.ERROR, logger="reflex_base.vars.base"):
        state.items = ["a"]  # pyright: ignore[reportAttributeAccessIssue]
        state.wrong_elements = ["b"]
        _ = state.as_ints
    name = type(state).__name__
    messages = [r.getMessage() for r in caplog.records]
    assert any(f"{name}.items" in m for m in messages) is element_error_logged
    assert any(f"{name}.as_ints" in m for m in messages) is element_error_logged

    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="reflex_base.vars.base"):
        state.items = "not a list"  # pyright: ignore[reportAttributeAccessIssue]
    assert any(f"{name}.items" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_cached_async_computed_var_checks_return_type_on_recompute_only(
    monkeypatch: pytest.MonkeyPatch,
):
    """A cached async computed var validates its return type only when it recomputes.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """

    class AsyncCheckedState(BaseState):
        items: list[int] = [1, 2, 3]

        @computed_var
        async def doubled(self) -> list[int]:
            return [i * 2 for i in self.items]

    cvar = AsyncCheckedState.computed_vars["doubled"]
    checked = []
    original = cvar._check_deprecated_return_type
    monkeypatch.setattr(
        type(cvar),
        "_check_deprecated_return_type",
        lambda self, instance, value: (
            checked.append(value) or original(instance, value)
        ),
    )
    state = AsyncCheckedState()

    assert await state.doubled == [2, 4, 6]
    assert await state.doubled == [2, 4, 6]
    assert checked == [[2, 4, 6]]

    state.items = [5]
    assert await state.doubled == [10]
    assert checked == [[2, 4, 6], [10]]


def test_private_names_are_not_fields():
    """A double-underscore name is a plain class attribute unless declared a field.

    A name-mangled private attribute, a hand-mangled one and a dunder stay
    ordinary attributes, as before fields became descriptors.
    """

    class Model(EvenMoreBasicBaseState):
        __mangled: int = 1  # pyright: ignore[reportGeneralTypeIssues]
        __unannotated = 2
        _Model__by_hand: int = 3
        __dunder__: int = 4
        __declared: Field[int] = field(default=5)  # pyright: ignore[reportGeneralTypeIssues]
        __unannotated_declared = field(default=6)  # pyright: ignore[reportGeneralTypeIssues]
        _backend: int = 7

    assert set(Model.__fields__) == {
        "_Model__declared",
        "_Model__unannotated_declared",
        "_backend",
    }
    assert Model.__fields__["_Model__declared"]._backend
    model = Model()
    for name, value in (
        ("_Model__mangled", 1),
        ("_Model__unannotated", 2),
        ("_Model__by_hand", 3),
        ("__dunder__", 4),
    ):
        assert vars(Model)[name] == value
        assert getattr(model, name) == value
    for name, value in (
        ("_Model__declared", 5),
        ("_Model__unannotated_declared", 6),
    ):
        assert getattr(model, name) == value


def test_private_names_of_plain_base_are_not_fields():
    """A plain base's private names are not fields of a model inheriting it either."""

    class Plain:
        __mangled: int = 1
        __dunder__: int = 2
        _backend: int = 3

    class Model(Plain, EvenMoreBasicBaseState):
        pass

    assert set(Model.__fields__) == {"_backend"}
    name = "_Plain__mangled"
    assert getattr(Model(), name) == 1


def test_new_default_for_inherited_private_field_stays_a_field():
    """A private name shadowing an inherited explicit field is a field as well."""

    class Parent(EvenMoreBasicBaseState):
        __counter__: Field[int] = field(default=1)

    class Annotated(Parent):
        __counter__: int = 2  # pyright: ignore[reportIncompatibleVariableOverride]

    class Unannotated(Parent):
        __counter__ = 2  # pyright: ignore[reportAssignmentType]

    for child in (Annotated, Unannotated):
        child_field = child.__fields__["__counter__"]
        assert child_field is not Parent.__fields__["__counter__"]
        assert child_field.default == 2
        assert isinstance(vars(child)["__counter__"], Field)
        assert child().__counter__ == 2
