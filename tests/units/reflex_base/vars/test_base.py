"""Tests for reflex_base.vars.base state metaclass field handling."""

import threading
import typing
from typing import Any, Literal

import pytest
from reflex_base.utils.types import get_field_type
from reflex_base.vars.base import EvenMoreBasicBaseState, Var, field
from reflex_base.vars.sequence import StringVar
from typing_extensions import TypeAliasType

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
def test_state_var_type_alias(alias_cls: type) -> None:
    """A state var annotated with a TypeAliasType compiles."""
    chart_key = alias_cls("ChartKey", Literal["day", "week"])

    class TypeAliasState(State):
        key: chart_key = "day"  # pyright: ignore[reportInvalidTypeForm]

    assert isinstance(TypeAliasState.key, StringVar)
    assert TypeAliasState.key._var_type == Literal["day", "week"]
