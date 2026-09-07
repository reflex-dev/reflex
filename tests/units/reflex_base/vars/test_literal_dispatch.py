"""Literal dispatch priority and extension behavior."""

import builtins
import dataclasses
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

import pytest
from reflex_base.utils.types import GenericType
from reflex_base.vars import base
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.number import LiteralNumberVar


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep test registrations out of the process-wide registry."""
    monkeypatch.setattr(base, "_var_subclasses", base._var_subclasses.copy())
    monkeypatch.setattr(
        base, "_var_literal_subclasses", base._var_literal_subclasses.copy()
    )
    yield
    base._clear_var_subclass_lookup_caches()


def register_literal(python_type: GenericType, marker: str) -> type[LiteralVar]:
    """Register a literal whose generated expression identifies its handler.

    Args:
        python_type: The registered Python type.
        marker: The generated expression and hook.

    Returns:
        The newly registered literal class.
    """

    class CustomVar(Var, python_types=python_type):
        """Var used to register one test type."""

    class CustomLiteral(LiteralVar, CustomVar):
        """Literal used to observe dispatch decisions."""

        @classmethod
        def create(cls, value: Any, _var_data: VarData | None = None) -> Var:
            """Create the marker Var for a selected value.

            Args:
                value: The selected value.
                _var_data: Additional Var metadata.

            Returns:
                The marker Var.
            """
            return cls(_js_expr=marker, _var_type=int, _var_data=_var_data)

        @classmethod
        def _get_all_var_data_without_creating_var(cls, value: Any) -> VarData:
            """Return marker metadata for a selected value.

            Args:
                value: The selected value.

            Returns:
                The marker metadata.
            """
            return VarData(hooks={marker: None})

    return CustomLiteral


def dispatch(value: Any, metadata: bool) -> Var | VarData | None:
    """Exercise either literal dispatcher with the same registry.

    Args:
        value: The value to dispatch.
        metadata: Whether to use the metadata dispatcher.

    Returns:
        The selected literal or metadata.
    """
    if metadata:
        return LiteralVar._get_all_var_data_without_creating_var_dispatch(value)
    return LiteralVar.create(value)


@pytest.mark.parametrize("metadata", [False, True])
def test_builtin_dispatch_skips_stable_isinstance_checks(
    metadata: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated builtin dispatch avoids rechecking ordinary registered types."""
    numeric_types = next(
        entry.python_types
        for literal, entry in base._var_literal_subclasses
        if literal is LiteralNumberVar
    )
    checks = []

    def record_isinstance(value: Any, classinfo: Any) -> bool:
        """Record the type tuples tested by the real dispatcher.

        Args:
            value: The dispatched value.
            classinfo: The type or tuple of types to test.

        Returns:
            The actual instance check result.
        """
        checks.append(classinfo)
        return builtins.isinstance(value, classinfo)

    monkeypatch.setattr(base, "isinstance", record_isinstance, raising=False)
    dispatch(42, metadata)
    checks.clear()
    dispatch(43, metadata)
    assert all(classinfo is not numeric_types for classinfo in checks)


@pytest.mark.parametrize("metadata", [False, True])
def test_literal_registration_invalidates_dispatch(metadata: bool) -> None:
    """A later literal registration still takes priority after cache warmup."""
    dispatch(1, metadata)
    register_literal(int, "first")
    result = dispatch(1, metadata)
    assert (
        result == VarData(hooks={"first": None}) if metadata else str(result) == "first"
    )
    register_literal(int, "second")
    result = dispatch(1, metadata)
    assert (
        result == VarData(hooks={"second": None})
        if metadata
        else str(result) == "second"
    )


@pytest.mark.parametrize("metadata", [False, True])
def test_value_sensitive_instance_checks_keep_priority(metadata: bool) -> None:
    """Custom metaclasses are checked for every value before stable matches."""
    checked = []

    class PositiveMeta(type):
        """Match positive integers without claiming all integer values."""

        def __instancecheck__(cls, value: Any) -> bool:
            checked.append(value)
            return type(value) is int and value > 0

    class Positive(metaclass=PositiveMeta):
        """Registered type with a value-dependent instance check."""

    register_literal(int, "ordinary")
    register_literal(Positive, "positive")
    for value, expected in [(0, "ordinary"), (1, "positive"), (-1, "ordinary")]:
        result = dispatch(value, metadata)
        assert (
            result == VarData(hooks={expected: None})
            if metadata
            else str(result) == expected
        )
    assert checked == [0, 1, -1]


@pytest.mark.parametrize("metadata", [False, True])
def test_abc_registration_remains_visible(metadata: bool) -> None:
    """Virtual ABC registration affects dispatch without a new literal class."""

    class VirtualABC(ABC):
        """ABC whose virtual subclasses change after cache warmup."""

        @abstractmethod
        def marker(self) -> None:
            """Identify implementations of this test ABC."""

    register_literal(int, "ordinary")
    register_literal(VirtualABC, "virtual")
    before = dispatch(1, metadata)
    assert (
        before == VarData(hooks={"ordinary": None})
        if metadata
        else str(before) == "ordinary"
    )
    VirtualABC.register(int)
    after = dispatch(1, metadata)
    assert (
        after == VarData(hooks={"virtual": None})
        if metadata
        else str(after) == "virtual"
    )


def test_dataclass_slots_replaces_cached_literal() -> None:
    """Recreated dataclass classes replace the original literal registration."""
    literal = register_literal(int, "custom")
    assert type(LiteralVar.create(1)) is literal
    recreated = dataclasses.dataclass(eq=False, frozen=True, slots=True)(literal)
    assert recreated is not literal
    assert type(LiteralVar.create(1)) is recreated


@pytest.mark.parametrize("metadata", [False, True])
def test_custom_values_keep_instance_class_behavior(metadata: bool) -> None:
    """Only exact builtin values may use type-based dispatch decisions."""

    class SpoofedInteger:
        """Expose an integer __class__ to Python's instance checks."""

        @property
        def __class__(self):
            return int

    register_literal(int, "integer")
    result = dispatch(SpoofedInteger(), metadata)
    assert (
        result == VarData(hooks={"integer": None})
        if metadata
        else str(result) == "integer"
    )
