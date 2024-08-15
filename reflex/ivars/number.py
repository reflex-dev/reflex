"""Immutable number vars."""

from __future__ import annotations

import dataclasses
import json
import sys
from functools import cached_property
from typing import Any, Union

from reflex.vars import ImmutableVarData, Var, VarData

from .base import (
    CachedVarOperation,
    ImmutableVar,
    LiteralVar,
    unionize,
)


class NumberVar(ImmutableVar[Union[int, float]]):
    """Base class for immutable number vars."""

    def __add__(self, other: number_types | boolean_types) -> NumberAddOperation:
        """Add two numbers.

        Args:
            other: The other number.

        Returns:
            The number addition operation.
        """
        return NumberAddOperation.create(self, +other)

    def __radd__(self, other: number_types | boolean_types) -> NumberAddOperation:
        """Add two numbers.

        Args:
            other: The other number.

        Returns:
            The number addition operation.
        """
        return NumberAddOperation.create(+other, self)

    def __sub__(self, other: number_types | boolean_types) -> NumberSubtractOperation:
        """Subtract two numbers.

        Args:
            other: The other number.

        Returns:
            The number subtraction operation.
        """
        return NumberSubtractOperation.create(self, +other)

    def __rsub__(self, other: number_types | boolean_types) -> NumberSubtractOperation:
        """Subtract two numbers.

        Args:
            other: The other number.

        Returns:
            The number subtraction operation.
        """
        return NumberSubtractOperation.create(+other, self)

    def __abs__(self) -> NumberAbsoluteOperation:
        """Get the absolute value of the number.

        Returns:
            The number absolute operation.
        """
        return NumberAbsoluteOperation.create(self)

    def __mul__(self, other: number_types | boolean_types) -> NumberMultiplyOperation:
        """Multiply two numbers.

        Args:
            other: The other number.

        Returns:
            The number multiplication operation.
        """
        return NumberMultiplyOperation.create(self, +other)

    def __rmul__(self, other: number_types | boolean_types) -> NumberMultiplyOperation:
        """Multiply two numbers.

        Args:
            other: The other number.

        Returns:
            The number multiplication operation.
        """
        return NumberMultiplyOperation.create(+other, self)

    def __truediv__(self, other: number_types | boolean_types) -> NumberTrueDivision:
        """Divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number true division operation.
        """
        return NumberTrueDivision.create(self, +other)

    def __rtruediv__(self, other: number_types | boolean_types) -> NumberTrueDivision:
        """Divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number true division operation.
        """
        return NumberTrueDivision.create(+other, self)

    def __floordiv__(self, other: number_types | boolean_types) -> NumberFloorDivision:
        """Floor divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number floor division operation.
        """
        return NumberFloorDivision.create(self, +other)

    def __rfloordiv__(self, other: number_types | boolean_types) -> NumberFloorDivision:
        """Floor divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number floor division operation.
        """
        return NumberFloorDivision.create(+other, self)

    def __mod__(self, other: number_types | boolean_types) -> NumberModuloOperation:
        """Modulo two numbers.

        Args:
            other: The other number.

        Returns:
            The number modulo operation.
        """
        return NumberModuloOperation.create(self, +other)

    def __rmod__(self, other: number_types | boolean_types) -> NumberModuloOperation:
        """Modulo two numbers.

        Args:
            other: The other number.

        Returns:
            The number modulo operation.
        """
        return NumberModuloOperation.create(+other, self)

    def __pow__(self, other: number_types | boolean_types) -> NumberExponentOperation:
        """Exponentiate two numbers.

        Args:
            other: The other number.

        Returns:
            The number exponent operation.
        """
        return NumberExponentOperation.create(self, +other)

    def __rpow__(self, other: number_types | boolean_types) -> NumberExponentOperation:
        """Exponentiate two numbers.

        Args:
            other: The other number.

        Returns:
            The number exponent operation.
        """
        return NumberExponentOperation.create(+other, self)

    def __neg__(self) -> NumberNegateOperation:
        """Negate the number.

        Returns:
            The number negation operation.
        """
        return NumberNegateOperation.create(self)

    def __invert__(self) -> BooleanNotOperation:
        """Boolean NOT the number.

        Returns:
            The boolean NOT operation.
        """
        return BooleanNotOperation.create(self.bool())

    def __pos__(self) -> NumberVar:
        """Positive the number.

        Returns:
            The number.
        """
        return self

    def __round__(self) -> NumberRoundOperation:
        """Round the number.

        Returns:
            The number round operation.
        """
        return NumberRoundOperation.create(self)

    def __ceil__(self) -> NumberCeilOperation:
        """Ceil the number.

        Returns:
            The number ceil operation.
        """
        return NumberCeilOperation.create(self)

    def __floor__(self) -> NumberFloorOperation:
        """Floor the number.

        Returns:
            The number floor operation.
        """
        return NumberFloorOperation.create(self)

    def __trunc__(self) -> NumberTruncOperation:
        """Trunc the number.

        Returns:
            The number trunc operation.
        """
        return NumberTruncOperation.create(self)

    def __lt__(self, other: Any) -> LessThanOperation:
        """Less than comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return LessThanOperation.create(self, +other)
        return LessThanOperation.create(self, other)

    def __le__(self, other: Any) -> LessThanOrEqualOperation:
        """Less than or equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return LessThanOrEqualOperation.create(self, +other)
        return LessThanOrEqualOperation.create(self, other)

    def __eq__(self, other: Any) -> EqualOperation:
        """Equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return EqualOperation.create(self, +other)
        return EqualOperation.create(self, other)

    def __ne__(self, other: Any) -> NotEqualOperation:
        """Not equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return NotEqualOperation.create(self, +other)
        return NotEqualOperation.create(self, other)

    def __gt__(self, other: Any) -> GreaterThanOperation:
        """Greater than comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return GreaterThanOperation.create(self, +other)
        return GreaterThanOperation.create(self, other)

    def __ge__(self, other: Any) -> GreaterThanOrEqualOperation:
        """Greater than or equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return GreaterThanOrEqualOperation.create(self, +other)
        return GreaterThanOrEqualOperation.create(self, other)

    def bool(self) -> NotEqualOperation:
        """Boolean conversion.

        Returns:
            The boolean value of the number.
        """
        return NotEqualOperation.create(self, 0)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class BinaryNumberOperation(CachedVarOperation, NumberVar):
    """Base class for immutable number vars that are the result of a binary operation."""

    _lhs: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )
    _rhs: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError(
            "BinaryNumberOperation must implement _cached_var_name"
        )

    @classmethod
    def create(
        cls, lhs: number_types, rhs: number_types, _var_data: VarData | None = None
    ):
        """Create the binary number operation var.

        Args:
            lhs: The first number.
            rhs: The second number.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The binary number operation var.
        """
        _lhs, _rhs = map(
            lambda v: LiteralNumberVar.create(v) if not isinstance(v, NumberVar) else v,
            (lhs, rhs),
        )
        return cls(
            _var_name="",
            _var_type=unionize(_lhs._var_type, _rhs._var_type),
            _var_data=ImmutableVarData.merge(_var_data),
            _lhs=_lhs,
            _rhs=_rhs,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class UnaryNumberOperation(CachedVarOperation, NumberVar):
    """Base class for immutable number vars that are the result of a unary operation."""

    _value: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(
            "UnaryNumberOperation must implement _cached_var_name"
        )

    @classmethod
    def create(cls, value: NumberVar, _var_data: VarData | None = None):
        """Create the unary number operation var.

        Args:
            value: The number.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The unary number operation var.
        """
        return cls(
            _var_name="",
            _var_type=value._var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


class NumberAddOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of an addition operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} + {str(self._rhs)})"


class NumberSubtractOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a subtraction operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} - {str(self._rhs)})"


class NumberAbsoluteOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of an absolute operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Math.abs({str(self._value)})"


class NumberMultiplyOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a multiplication operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} * {str(self._rhs)})"


class NumberNegateOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a negation operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"-({str(self._value)})"


class NumberTrueDivision(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a true division operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} / {str(self._rhs)})"


class NumberFloorDivision(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a floor division operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Math.floor({str(self._lhs)} / {str(self._rhs)})"


class NumberModuloOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a modulo operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} % {str(self._rhs)})"


class NumberExponentOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of an exponent operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} ** {str(self._rhs)})"


class NumberRoundOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a round operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Math.round({str(self._value)})"


class NumberCeilOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a ceil operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Math.ceil({str(self._value)})"


class NumberFloorOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a floor operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Math.floor({str(self._value)})"


class NumberTruncOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a trunc operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Math.trunc({str(self._value)})"


class BooleanVar(ImmutableVar[bool]):
    """Base class for immutable boolean vars."""

    def __invert__(self) -> BooleanNotOperation:
        """NOT the boolean.

        Returns:
            The boolean NOT operation.
        """
        return BooleanNotOperation.create(self)

    def __int__(self) -> BooleanToIntOperation:
        """Convert the boolean to an int.

        Returns:
            The boolean to int operation.
        """
        return BooleanToIntOperation.create(self)

    def __pos__(self) -> BooleanToIntOperation:
        """Convert the boolean to an int.

        Returns:
            The boolean to int operation.
        """
        return BooleanToIntOperation.create(self)

    def bool(self) -> BooleanVar:
        """Boolean conversion.

        Returns:
            The boolean value of the boolean.
        """
        return self

    def __lt__(self, other: boolean_types | number_types) -> LessThanOperation:
        """Less than comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return LessThanOperation.create(+self, +other)

    def __le__(self, other: boolean_types | number_types) -> LessThanOrEqualOperation:
        """Less than or equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return LessThanOrEqualOperation.create(+self, +other)

    def __eq__(self, other: boolean_types | number_types) -> EqualOperation:
        """Equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return EqualOperation.create(+self, +other)

    def __ne__(self, other: boolean_types | number_types) -> NotEqualOperation:
        """Not equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return NotEqualOperation.create(+self, +other)

    def __gt__(self, other: boolean_types | number_types) -> GreaterThanOperation:
        """Greater than comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return GreaterThanOperation.create(+self, +other)

    def __ge__(
        self, other: boolean_types | number_types
    ) -> GreaterThanOrEqualOperation:
        """Greater than or equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return GreaterThanOrEqualOperation.create(+self, +other)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class BooleanToIntOperation(CachedVarOperation, NumberVar):
    """Base class for immutable number vars that are the result of a boolean to int operation."""

    _value: BooleanVar = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._value)} ? 1 : 0)"

    @classmethod
    def create(cls, value: BooleanVar, _var_data: VarData | None = None):
        """Create the boolean to int operation var.

        Args:
            value: The boolean.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The boolean to int operation var.
        """
        return cls(
            _var_name="",
            _var_type=int,
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ComparisonOperation(CachedVarOperation, BooleanVar):
    """Base class for immutable boolean vars that are the result of a comparison operation."""

    _lhs: Var = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )
    _rhs: Var = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError("ComparisonOperation must implement _cached_var_name")

    @classmethod
    def create(cls, lhs: Var | Any, rhs: Var | Any, _var_data: VarData | None = None):
        """Create the comparison operation var.

        Args:
            lhs: The first value.
            rhs: The second value.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The comparison operation var.
        """
        lhs, rhs = map(LiteralVar.create, (lhs, rhs))
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _lhs=lhs,
            _rhs=rhs,
        )


class GreaterThanOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a greater than operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} > {str(self._rhs)})"


class GreaterThanOrEqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a greater than or equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} >= {str(self._rhs)})"


class LessThanOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a less than operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} < {str(self._rhs)})"


class LessThanOrEqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a less than or equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} <= {str(self._rhs)})"


class EqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of an equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} === {str(self._rhs)})"


class NotEqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a not equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._lhs)} !== {str(self._rhs)})"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LogicalOperation(CachedVarOperation, BooleanVar):
    """Base class for immutable boolean vars that are the result of a logical operation."""

    _lhs: BooleanVar = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )
    _rhs: BooleanVar = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError("LogicalOperation must implement _cached_var_name")

    @classmethod
    def create(
        cls, lhs: boolean_types, rhs: boolean_types, _var_data: VarData | None = None
    ):
        """Create the logical operation var.

        Args:
            lhs: The first boolean.
            rhs: The second boolean.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The logical operation var.
        """
        lhs, rhs = map(
            lambda v: (
                LiteralBooleanVar.create(v) if not isinstance(v, BooleanVar) else v
            ),
            (lhs, rhs),
        )
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _lhs=lhs,
            _rhs=rhs,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class BooleanNotOperation(CachedVarOperation, BooleanVar):
    """Base class for immutable boolean vars that are the result of a logical NOT operation."""

    _value: BooleanVar = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"!({str(self._value)})"

    @classmethod
    def create(cls, value: boolean_types, _var_data: VarData | None = None):
        """Create the logical NOT operation var.

        Args:
            value: The value.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The logical NOT operation var.
        """
        value = value if isinstance(value, Var) else LiteralBooleanVar.create(value)
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralBooleanVar(LiteralVar, BooleanVar):
    """Base class for immutable literal boolean vars."""

    _var_value: bool = dataclasses.field(default=False)

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return "true" if self._var_value else "false"

    def __hash__(self) -> int:
        """Calculate the hash value of the object.

        Returns:
            int: The hash value of the object.
        """
        return hash((self.__class__.__name__, self._var_value))

    @classmethod
    def create(cls, value: bool, _var_data: VarData | None = None):
        """Create the boolean var.

        Args:
            value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The boolean var.
        """
        return cls(
            _var_name="true" if value else "false",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _var_value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralNumberVar(LiteralVar, NumberVar):
    """Base class for immutable literal number vars."""

    _var_value: float | int = dataclasses.field(default=0)

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return json.dumps(self._var_value)

    def __hash__(self) -> int:
        """Calculate the hash value of the object.

        Returns:
            int: The hash value of the object.
        """
        return hash((self.__class__.__name__, self._var_value))

    @classmethod
    def create(cls, value: float | int, _var_data: VarData | None = None):
        """Create the number var.

        Args:
            value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The number var.
        """
        return cls(
            _var_name=str(value),
            _var_type=type(value),
            _var_data=ImmutableVarData.merge(_var_data),
            _var_value=value,
        )


number_types = Union[NumberVar, int, float]
boolean_types = Union[BooleanVar, bool]


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToNumberVarOperation(CachedVarOperation, NumberVar):
    """Base class for immutable number vars that are the result of a number operation."""

    _original_value: Var = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return str(self._original_value)

    @classmethod
    def create(
        cls,
        value: Var,
        _var_type: type[int] | type[float] = float,
        _var_data: VarData | None = None,
    ):
        """Create the number var.

        Args:
            value: The value of the var.
            _var_type: The type of the Var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The number var.
        """
        return cls(
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _original_value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToBooleanVarOperation(CachedVarOperation, BooleanVar):
    """Base class for immutable boolean vars that are the result of a boolean operation."""

    _original_value: Var = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Boolean({str(self._original_value)})"

    @classmethod
    def create(
        cls,
        value: Var,
        _var_data: VarData | None = None,
    ):
        """Create the boolean var.

        Args:
            value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The boolean var.
        """
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _original_value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class TernaryOperator(CachedVarOperation, ImmutableVar):
    """Base class for immutable vars that are the result of a ternary operation."""

    _condition: BooleanVar = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar.create(False)
    )
    _if_true: Var = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )
    _if_false: Var = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            f"({str(self._condition)} ? {str(self._if_true)} : {str(self._if_false)})"
        )

    @classmethod
    def create(
        cls,
        condition: boolean_types,
        if_true: Var | Any,
        if_false: Var | Any,
        _var_data: VarData | None = None,
    ):
        """Create the ternary operation var.

        Args:
            condition: The condition.
            if_true: The value if the condition is true.
            if_false: The value if the condition is false.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The ternary operation var.
        """
        condition = (
            condition
            if isinstance(condition, Var)
            else LiteralBooleanVar.create(condition)
        )
        _if_true, _if_false = map(
            lambda v: (LiteralVar.create(v) if not isinstance(v, Var) else v),
            (if_true, if_false),
        )
        return TernaryOperator(
            _var_name="",
            _var_type=unionize(_if_true._var_type, _if_false._var_type),
            _var_data=ImmutableVarData.merge(_var_data),
            _condition=condition,
            _if_true=_if_true,
            _if_false=_if_false,
        )
