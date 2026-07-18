"""Tests for reflex_base.vars.base state metaclass field handling."""

from typing import Any

from reflex_base.utils.types import get_field_type
from reflex_base.vars.base import EvenMoreBasicBaseState, field

import reflex as rx
from reflex.state import BaseState

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


def test_custom_mutable_attr_is_deepcopied():
    """Mutable custom attrs are deep-copied, not shared by reference."""
    f = field("x")
    opts = {"a": [1]}
    f._opts = opts  # pyright: ignore[reportAttributeAccessIssue]

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert rebuilt._opts == {"a": [1]}  # pyright: ignore[reportAttributeAccessIssue]
    assert rebuilt._opts is not opts  # pyright: ignore[reportAttributeAccessIssue]
    opts["a"].append(2)
    assert rebuilt._opts == {"a": [1]}  # pyright: ignore[reportAttributeAccessIssue]


def test_computed_var_return_type_checked_only_on_recompute(mocker):
    """The return type of a cached computed var is only validated on recompute.

    Args:
        mocker: Pytest mocker object.
    """

    class ReturnTypeCheckState(BaseState):
        v: int = 0

        @rx.var
        def wrong_typed(self) -> str:
            return self.v  # pyright: ignore [reportReturnType]

    state = ReturnTypeCheckState()
    mock_error = mocker.patch("reflex_base.utils.console.error")
    assert state.wrong_typed == 0
    assert mock_error.call_count == 1
    # Cache hits must not re-run the (potentially deep) type check.
    assert state.wrong_typed == 0
    assert mock_error.call_count == 1
    # Invalidation triggers a recompute, which re-checks the return type.
    state.v = 1
    assert state.wrong_typed == 1
    assert mock_error.call_count == 2


def test_non_cached_computed_var_return_type_checked_every_access(mocker):
    """A cache=False computed var recomputes, and is type-checked, on every access.

    Args:
        mocker: Pytest mocker object.
    """

    class NonCachedReturnTypeCheckState(BaseState):
        v: int = 0

        @rx.var(cache=False)
        def wrong_typed(self) -> str:
            return self.v  # pyright: ignore [reportReturnType]

    state = NonCachedReturnTypeCheckState()
    mock_error = mocker.patch("reflex_base.utils.console.error")
    assert state.wrong_typed == 0
    assert state.wrong_typed == 0
    assert mock_error.call_count == 2


async def test_async_computed_var_return_type_checked_only_on_recompute(mocker):
    """The return type of a cached async computed var is only validated on recompute.

    Args:
        mocker: Pytest mocker object.
    """

    class AsyncReturnTypeCheckState(BaseState):
        v: int = 0

        @rx.var
        async def wrong_typed(self) -> str:
            return self.v  # pyright: ignore [reportReturnType]

    state = AsyncReturnTypeCheckState()
    mock_error = mocker.patch("reflex_base.utils.console.error")
    assert await state.wrong_typed == 0
    assert mock_error.call_count == 1
    # Cache hits must not re-run the (potentially deep) type check.
    assert await state.wrong_typed == 0
    assert mock_error.call_count == 1
