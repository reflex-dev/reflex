"""Tests for reflex_base.vars.base state metaclass field handling."""

import threading
from typing import Any

from reflex_base.utils.types import get_field_type
from reflex_base.vars.base import EvenMoreBasicBaseState, field

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
    """Custom attrs are carried onto the rebuilt Field as the same objects.

    The source Field is a throwaway namespace value replaced during class
    creation, so sharing is safe — and identity is what tag consumers rely on
    (matching how ``_copy_fn`` carries a function's ``__dict__``).
    """
    f = field("x")
    opts = {"a": [1]}
    f._opts = opts  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert rebuilt._opts is opts  # pyright: ignore[reportAttributeAccessIssue]


def test_custom_callable_attr_survives_by_identity():
    """A callable-object custom attr is not cloned by the rebuild.

    Downstream markers (e.g. auth check objects) may be stateful; the rebuilt
    field must expose the original instance, not a copy.
    """

    class Check:
        def __call__(self) -> bool:
            return True

    check = Check()
    f = field("x")
    f._check = check  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert rebuilt._check is check  # pyright: ignore[reportAttributeAccessIssue]


def test_non_copyable_custom_attr_does_not_break_class_creation():
    """A custom attr holding non-copyable state must not crash class creation.

    Regression: deep-copying carried attrs raised ``TypeError: cannot pickle
    '_thread.lock' object`` for markers holding locks, clients, or similar.
    """

    class Guard:
        def __init__(self) -> None:
            self.lock = threading.Lock()

    guard = Guard()
    f = field("x")
    f._guard = guard  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert rebuilt._guard is guard  # pyright: ignore[reportAttributeAccessIssue]
