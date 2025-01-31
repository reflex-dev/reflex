"""Immutable datetime and date vars."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from typing import TypeVar, Union

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


def date_compare_operation(
    lhs: Var[datetime_types],
    rhs: Var[datetime_types],
    strict: bool = False,
) -> CustomVarOperationReturn[bool]:
    """Check if the value is less than the other value.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.
        strict: Whether to use strict comparison.

    Returns:
        The result of the operation.
    """
    return var_operation_return(
        f"({lhs} { '<' if strict else '<='} {rhs})",
        bool,
    )


@var_operation
def date_gt_operation(
    lhs: Var[datetime_types],
    rhs: Var[datetime_types],
) -> CustomVarOperationReturn:
    """Greater than comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(rhs, lhs, strict=True)


@var_operation
def date_lt_operation(
    lhs: Var[datetime_types],
    rhs: Var[datetime_types],
) -> CustomVarOperationReturn:
    """Less than comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(lhs, rhs, strict=True)


@var_operation
def date_le_operation(
    lhs: Var[datetime_types], rhs: Var[datetime_types]
) -> CustomVarOperationReturn:
    """Less than or equal comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(lhs, rhs)


@var_operation
def date_ge_operation(
    lhs: Var[datetime_types], rhs: Var[datetime_types]
) -> CustomVarOperationReturn:
    """Greater than or equal comparison.

    Args:
        lhs: The left-hand side of the operation.
        rhs: The right-hand side of the operation.

    Returns:
        The result of the operation.
    """
    return date_compare_operation(rhs, lhs)


class DateTimeVar(Var[DATETIME_T], python_types=(datetime, date)):
    """A variable that holds a datetime or date object."""

    __lt__ = date_lt_operation

    __le__ = date_le_operation

    __gt__ = date_gt_operation

    __ge__ = date_ge_operation


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
