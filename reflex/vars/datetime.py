"""Immutable datetime and date vars."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import Any, NoReturn, TypeVar, Union, overload

from reflex.utils.exceptions import VarTypeError
from reflex.vars.number import BooleanVar

from .base import (
    CustomVarOperationReturn,
    LiteralVar,
    Var,
    VarData,
    var_operation,
    var_operation_return,
)

DATETIME_T = TypeVar("DATETIME_T", datetime, date)

datetime_types = Union[datetime, date]


def raise_var_type_error():
    """Raise a VarTypeError.

    Raises:
        VarTypeError: Cannot compare a datetime object with a non-datetime object.
    """
    raise VarTypeError("Cannot compare a datetime object with a non-datetime object.")


class DateTimeVar(Var[DATETIME_T], python_types=(datetime, date)):
    """A variable that holds a datetime or date object."""

    @overload
    def __lt__(self, other: datetime_types) -> BooleanVar: ...

    @overload
    def __lt__(self, other: NoReturn) -> NoReturn: ...  # pyright: ignore [reportOverlappingOverload]

    def __lt__(self, other: Any):
        """Less than comparison.

        Args:
            other: The other datetime to compare.

        Returns:
            The result of the comparison.
        """
        if not isinstance(other, DATETIME_TYPES):
            raise_var_type_error()
        return date_lt_operation(self, other)

    @overload
    def __le__(self, other: datetime_types) -> BooleanVar: ...

    @overload
    def __le__(self, other: NoReturn) -> NoReturn: ...  # pyright: ignore [reportOverlappingOverload]

    def __le__(self, other: Any):
        """Less than or equal comparison.

        Args:
            other: The other datetime to compare.

        Returns:
            The result of the comparison.
        """
        if not isinstance(other, DATETIME_TYPES):
            raise_var_type_error()
        return date_le_operation(self, other)

    @overload
    def __gt__(self, other: datetime_types) -> BooleanVar: ...

    @overload
    def __gt__(self, other: NoReturn) -> NoReturn: ...  # pyright: ignore [reportOverlappingOverload]

    def __gt__(self, other: Any):
        """Greater than comparison.

        Args:
            other: The other datetime to compare.

        Returns:
            The result of the comparison.
        """
        if not isinstance(other, DATETIME_TYPES):
            raise_var_type_error()
        return date_gt_operation(self, other)

    @overload
    def __ge__(self, other: datetime_types) -> BooleanVar: ...

    @overload
    def __ge__(self, other: NoReturn) -> NoReturn: ...  # pyright: ignore [reportOverlappingOverload]

    def __ge__(self, other: Any):
        """Greater than or equal comparison.

        Args:
            other: The other datetime to compare.

        Returns:
            The result of the comparison.
        """
        if not isinstance(other, DATETIME_TYPES):
            raise_var_type_error()
        return date_ge_operation(self, other)


@var_operation
def date_gt_operation(lhs: Var | Any, rhs: Var | Any) -> CustomVarOperationReturn:
    """Greater than comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(rhs, lhs, strict=True)


@var_operation
def date_lt_operation(lhs: Var | Any, rhs: Var | Any) -> CustomVarOperationReturn:
    """Less than comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(lhs, rhs, strict=True)


@var_operation
def date_le_operation(lhs: Var | Any, rhs: Var | Any) -> CustomVarOperationReturn:
    """Less than or equal comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(lhs, rhs)


@var_operation
def date_ge_operation(lhs: Var | Any, rhs: Var | Any) -> CustomVarOperationReturn:
    """Greater than or equal comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(rhs, lhs)


def date_compare_operation(
    lhs: DateTimeVar[DATETIME_T] | Any,
    rhs: DateTimeVar[DATETIME_T] | Any,
    strict: bool = False,
) -> CustomVarOperationReturn:
    """Check if the value is less than the other value.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.
        strict: Whether to use strict comparison.

    Returns:
        The result of the operation.
    """
    return var_operation_return(
        f"({lhs} {'<' if strict else '<='} {rhs})",
        bool,
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralDatetimeVar(LiteralVar, DateTimeVar):
    """Base class for immutable datetime and date vars."""

    _var_value: datetime | date = dataclasses.field(default=datetime.now())

    @classmethod
    def create(cls, value: datetime | date, _var_data: VarData | None = None):
        """Create a new instance of the class.

        Args:
            value: The value to set.

        Returns:
            LiteralDatetimeVar: The new instance of the class.
        """
        js_expr = f'"{value!s}"'
        return cls(
            _js_expr=js_expr,
            _var_type=type(value),
            _var_value=value,
            _var_data=_var_data,
        )


DATETIME_TYPES = (datetime, date, DateTimeVar)
