"""Immutable number vars."""

from __future__ import annotations

import dataclasses
import json
import sys
from functools import cached_property
from typing import Any, Union

from reflex.utils.types import GenericType

from .base import (
    ImmutableVar,
    LiteralVar,
)
from reflex.vars import ImmutableVarData, Var, VarData


class NumberVar(ImmutableVar[Union[int, float]]):
    """Base class for immutable number vars."""

    def __add__(self, other: number_types | boolean_types) -> NumberAddOperation:
        """Add two numbers.

        Args:
            other: The other number.

        Returns:
            The number addition operation.
        """
        return NumberAddOperation(self, +other)

    def __radd__(self, other: number_types | boolean_types) -> NumberAddOperation:
        """Add two numbers.

        Args:
            other: The other number.

        Returns:
            The number addition operation.
        """
        return NumberAddOperation(+other, self)

    def __sub__(self, other: number_types | boolean_types) -> NumberSubtractOperation:
        """Subtract two numbers.

        Args:
            other: The other number.

        Returns:
            The number subtraction operation.
        """
        return NumberSubtractOperation(self, +other)

    def __rsub__(self, other: number_types | boolean_types) -> NumberSubtractOperation:
        """Subtract two numbers.

        Args:
            other: The other number.

        Returns:
            The number subtraction operation.
        """
        return NumberSubtractOperation(+other, self)

    def __abs__(self) -> NumberAbsoluteOperation:
        """Get the absolute value of the number.

        Returns:
            The number absolute operation.
        """
        return NumberAbsoluteOperation(self)

    def __mul__(self, other: number_types | boolean_types) -> NumberMultiplyOperation:
        """Multiply two numbers.

        Args:
            other: The other number.

        Returns:
            The number multiplication operation.
        """
        return NumberMultiplyOperation(self, +other)

    def __rmul__(self, other: number_types | boolean_types) -> NumberMultiplyOperation:
        """Multiply two numbers.

        Args:
            other: The other number.

        Returns:
            The number multiplication operation.
        """
        return NumberMultiplyOperation(+other, self)

    def __truediv__(self, other: number_types | boolean_types) -> NumberTrueDivision:
        """Divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number true division operation.
        """
        return NumberTrueDivision(self, +other)

    def __rtruediv__(self, other: number_types | boolean_types) -> NumberTrueDivision:
        """Divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number true division operation.
        """
        return NumberTrueDivision(+other, self)

    def __floordiv__(self, other: number_types | boolean_types) -> NumberFloorDivision:
        """Floor divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number floor division operation.
        """
        return NumberFloorDivision(self, +other)

    def __rfloordiv__(self, other: number_types | boolean_types) -> NumberFloorDivision:
        """Floor divide two numbers.

        Args:
            other: The other number.

        Returns:
            The number floor division operation.
        """
        return NumberFloorDivision(+other, self)

    def __mod__(self, other: number_types | boolean_types) -> NumberModuloOperation:
        """Modulo two numbers.

        Args:
            other: The other number.

        Returns:
            The number modulo operation.
        """
        return NumberModuloOperation(self, +other)

    def __rmod__(self, other: number_types | boolean_types) -> NumberModuloOperation:
        """Modulo two numbers.

        Args:
            other: The other number.

        Returns:
            The number modulo operation.
        """
        return NumberModuloOperation(+other, self)

    def __pow__(self, other: number_types | boolean_types) -> NumberExponentOperation:
        """Exponentiate two numbers.

        Args:
            other: The other number.

        Returns:
            The number exponent operation.
        """
        return NumberExponentOperation(self, +other)

    def __rpow__(self, other: number_types | boolean_types) -> NumberExponentOperation:
        """Exponentiate two numbers.

        Args:
            other: The other number.

        Returns:
            The number exponent operation.
        """
        return NumberExponentOperation(+other, self)

    def __neg__(self) -> NumberNegateOperation:
        """Negate the number.

        Returns:
            The number negation operation.
        """
        return NumberNegateOperation(self)

    def __invert__(self) -> BooleanNotOperation:
        """Boolean NOT the number.

        Returns:
            The boolean NOT operation.
        """
        return BooleanNotOperation(self.bool())

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
        return NumberRoundOperation(self)

    def __ceil__(self) -> NumberCeilOperation:
        """Ceil the number.

        Returns:
            The number ceil operation.
        """
        return NumberCeilOperation(self)

    def __floor__(self) -> NumberFloorOperation:
        """Floor the number.

        Returns:
            The number floor operation.
        """
        return NumberFloorOperation(self)

    def __trunc__(self) -> NumberTruncOperation:
        """Trunc the number.

        Returns:
            The number trunc operation.
        """
        return NumberTruncOperation(self)

    def __lt__(self, other: Any) -> LessThanOperation:
        """Less than comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return LessThanOperation(self, +other)
        return LessThanOperation(self, other)

    def __le__(self, other: Any) -> LessThanOrEqualOperation:
        """Less than or equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return LessThanOrEqualOperation(self, +other)
        return LessThanOrEqualOperation(self, other)

    def __eq__(self, other: Any) -> EqualOperation:
        """Equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return EqualOperation(self, +other)
        return EqualOperation(self, other)

    def __ne__(self, other: Any) -> NotEqualOperation:
        """Not equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return NotEqualOperation(self, +other)
        return NotEqualOperation(self, other)

    def __gt__(self, other: Any) -> GreaterThanOperation:
        """Greater than comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return GreaterThanOperation(self, +other)
        return GreaterThanOperation(self, other)

    def __ge__(self, other: Any) -> GreaterThanOrEqualOperation:
        """Greater than or equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        if isinstance(other, (NumberVar, BooleanVar, int, float, bool)):
            return GreaterThanOrEqualOperation(self, +other)
        return GreaterThanOrEqualOperation(self, other)

    def bool(self) -> NotEqualOperation:
        """Boolean conversion.

        Returns:
            The boolean value of the number.
        """
        return NotEqualOperation(self, 0)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class BinaryNumberOperation(NumberVar):
    """Base class for immutable number vars that are the result of a binary operation."""

    a: number_types = dataclasses.field(default=0)
    b: number_types = dataclasses.field(default=0)

    def __init__(
        self,
        a: number_types,
        b: number_types,
        _var_data: VarData | None = None,
    ):
        """Initialize the binary number operation var.

        Args:
            a: The first number.
            b: The second number.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(BinaryNumberOperation, self).__init__(
            _var_name="",
            _var_type=float,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "b", b)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError(
            "BinaryNumberOperation must implement _cached_var_name"
        )

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(BinaryNumberOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return ImmutableVarData.merge(
            first_value._get_all_var_data(),
            second_value._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class UnaryNumberOperation(NumberVar):
    """Base class for immutable number vars that are the result of a unary operation."""

    a: number_types = dataclasses.field(default=0)

    def __init__(
        self,
        a: number_types,
        _var_data: VarData | None = None,
    ):
        """Initialize the unary number operation var.

        Args:
            a: The number.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(UnaryNumberOperation, self).__init__(
            _var_name="",
            _var_type=float,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(
            "UnaryNumberOperation must implement _cached_var_name"
        )

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(UnaryNumberOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        return ImmutableVarData.merge(value._get_all_var_data(), self._var_data)

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class NumberAddOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of an addition operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return f"({str(first_value)} + {str(second_value)})"


class NumberSubtractOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a subtraction operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return f"({str(first_value)} - {str(second_value)})"


class NumberAbsoluteOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of an absolute operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        return f"Math.abs({str(value)})"


class NumberMultiplyOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a multiplication operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return f"({str(first_value)} * {str(second_value)})"


class NumberNegateOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a negation operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        return f"-({str(value)})"


class NumberTrueDivision(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a true division operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return f"({str(first_value)} / {str(second_value)})"


class NumberFloorDivision(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a floor division operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return f"Math.floor({str(first_value)} / {str(second_value)})"


class NumberModuloOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of a modulo operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return f"({str(first_value)} % {str(second_value)})"


class NumberExponentOperation(BinaryNumberOperation):
    """Base class for immutable number vars that are the result of an exponent operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralNumberVar(self.b)
        return f"({str(first_value)} ** {str(second_value)})"


class NumberRoundOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a round operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        return f"Math.round({str(value)})"


class NumberCeilOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a ceil operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        return f"Math.ceil({str(value)})"


class NumberFloorOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a floor operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        return f"Math.floor({str(value)})"


class NumberTruncOperation(UnaryNumberOperation):
    """Base class for immutable number vars that are the result of a trunc operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        value = self.a if isinstance(self.a, Var) else LiteralNumberVar(self.a)
        return f"Math.trunc({str(value)})"


class BooleanVar(ImmutableVar[bool]):
    """Base class for immutable boolean vars."""

    def __invert__(self) -> BooleanNotOperation:
        """NOT the boolean.

        Returns:
            The boolean NOT operation.
        """
        return BooleanNotOperation(self)

    def __int__(self) -> BooleanToIntOperation:
        """Convert the boolean to an int.

        Returns:
            The boolean to int operation.
        """
        return BooleanToIntOperation(self)

    def __pos__(self) -> BooleanToIntOperation:
        """Convert the boolean to an int.

        Returns:
            The boolean to int operation.
        """
        return BooleanToIntOperation(self)

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
        return LessThanOperation(+self, +other)

    def __le__(self, other: boolean_types | number_types) -> LessThanOrEqualOperation:
        """Less than or equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return LessThanOrEqualOperation(+self, +other)

    def __eq__(self, other: boolean_types | number_types) -> EqualOperation:
        """Equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return EqualOperation(+self, +other)

    def __ne__(self, other: boolean_types | number_types) -> NotEqualOperation:
        """Not equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return NotEqualOperation(+self, +other)

    def __gt__(self, other: boolean_types | number_types) -> GreaterThanOperation:
        """Greater than comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return GreaterThanOperation(+self, +other)

    def __ge__(
        self, other: boolean_types | number_types
    ) -> GreaterThanOrEqualOperation:
        """Greater than or equal comparison.

        Args:
            other: The other boolean.

        Returns:
            The result of the comparison.
        """
        return GreaterThanOrEqualOperation(+self, +other)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class BooleanToIntOperation(NumberVar):
    """Base class for immutable number vars that are the result of a boolean to int operation."""

    a: boolean_types = dataclasses.field(default=False)

    def __init__(
        self,
        a: boolean_types,
        _var_data: VarData | None = None,
    ):
        """Initialize the boolean to int operation var.

        Args:
            a: The boolean.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(BooleanToIntOperation, self).__init__(
            _var_name="",
            _var_type=int,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self.a)} ? 1 : 0)"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(BooleanToIntOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data() if isinstance(self.a, Var) else None,
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ComparisonOperation(BooleanVar):
    """Base class for immutable boolean vars that are the result of a comparison operation."""

    a: Var = dataclasses.field(default_factory=lambda: LiteralBooleanVar(True))
    b: Var = dataclasses.field(default_factory=lambda: LiteralBooleanVar(True))

    def __init__(
        self,
        a: Var | Any,
        b: Var | Any,
        _var_data: VarData | None = None,
    ):
        """Initialize the comparison operation var.

        Args:
            a: The first value.
            b: The second value.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ComparisonOperation, self).__init__(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a if isinstance(a, Var) else LiteralVar.create(a))
        object.__setattr__(self, "b", b if isinstance(b, Var) else LiteralVar.create(b))
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError("ComparisonOperation must implement _cached_var_name")

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ComparisonOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return ImmutableVarData.merge(
            first_value._get_all_var_data(), second_value._get_all_var_data()
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class GreaterThanOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a greater than operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} > {str(second_value)})"


class GreaterThanOrEqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a greater than or equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} >= {str(second_value)})"


class LessThanOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a less than operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} < {str(second_value)})"


class LessThanOrEqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a less than or equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} <= {str(second_value)})"


class EqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of an equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} === {str(second_value)})"


class NotEqualOperation(ComparisonOperation):
    """Base class for immutable boolean vars that are the result of a not equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} != {str(second_value)})"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LogicalOperation(BooleanVar):
    """Base class for immutable boolean vars that are the result of a logical operation."""

    a: boolean_types = dataclasses.field(default=False)
    b: boolean_types = dataclasses.field(default=False)

    def __init__(
        self, a: boolean_types, b: boolean_types, _var_data: VarData | None = None
    ):
        """Initialize the logical operation var.

        Args:
            a: The first value.
            b: The second value.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LogicalOperation, self).__init__(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "b", b)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError("LogicalOperation must implement _cached_var_name")

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(LogicalOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return ImmutableVarData.merge(
            first_value._get_all_var_data(), second_value._get_all_var_data()
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class BooleanNotOperation(BooleanVar):
    """Base class for immutable boolean vars that are the result of a logical NOT operation."""

    a: boolean_types = dataclasses.field()

    def __init__(self, a: boolean_types, _var_data: VarData | None = None):
        """Initialize the logical NOT operation var.

        Args:
            a: The value.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(BooleanNotOperation, self).__init__(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        return f"!({str(value)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(BooleanNotOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        return ImmutableVarData.merge(value._get_all_var_data())

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralBooleanVar(LiteralVar, BooleanVar):
    """Base class for immutable literal boolean vars."""

    _var_value: bool = dataclasses.field(default=False)

    def __init__(
        self,
        _var_value: bool,
        _var_data: VarData | None = None,
    ):
        """Initialize the boolean var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralBooleanVar, self).__init__(
            _var_name="true" if _var_value else "false",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_var_value", _var_value)

    def __hash__(self) -> int:
        """Hash the var.

        Returns:
            The hash of the var.
        """
        return hash((self.__class__.__name__, self._var_value))

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return "true" if self._var_value else "false"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralNumberVar(LiteralVar, NumberVar):
    """Base class for immutable literal number vars."""

    _var_value: float | int = dataclasses.field(default=0)

    def __init__(
        self,
        _var_value: float | int,
        _var_data: VarData | None = None,
    ):
        """Initialize the number var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralNumberVar, self).__init__(
            _var_name=str(_var_value),
            _var_type=type(_var_value),
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_var_value", _var_value)

    def __hash__(self) -> int:
        """Hash the var.

        Returns:
            The hash of the var.
        """
        return hash((self.__class__.__name__, self._var_value))

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return json.dumps(self._var_value)


number_types = Union[NumberVar, LiteralNumberVar, int, float]
boolean_types = Union[BooleanVar, LiteralBooleanVar, bool]


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToNumberVarOperation(NumberVar):
    """Base class for immutable number vars that are the result of a number operation."""

    _original_value: Var = dataclasses.field(
        default_factory=lambda: LiteralNumberVar(0)
    )

    def __init__(
        self,
        _original_value: Var,
        _var_type: type[int] | type[float] = float,
        _var_data: VarData | None = None,
    ):
        """Initialize the number var.

        Args:
            _original_value: The original value.
            _var_type: The type of the Var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ToNumberVarOperation, self).__init__(
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_original_value", _original_value)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return str(self._original_value)

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ToNumberVarOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._original_value._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToBooleanVarOperation(BooleanVar):
    """Base class for immutable boolean vars that are the result of a boolean operation."""

    _original_value: Var = dataclasses.field(
        default_factory=lambda: LiteralBooleanVar(False)
    )

    def __init__(
        self,
        _original_value: Var,
        _var_data: VarData | None = None,
    ):
        """Initialize the boolean var.

        Args:
            _original_value: The original value.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ToBooleanVarOperation, self).__init__(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_original_value", _original_value)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Boolean({str(self._original_value)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ToBooleanVarOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._original_value._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class TernaryOperator(ImmutableVar):
    """Base class for immutable vars that are the result of a ternary operation."""

    condition: Var = dataclasses.field(default_factory=lambda: LiteralBooleanVar(False))
    if_true: Var = dataclasses.field(default_factory=lambda: LiteralNumberVar(0))
    if_false: Var = dataclasses.field(default_factory=lambda: LiteralNumberVar(0))

    def __init__(
        self,
        condition: Var | Any,
        if_true: Var | Any,
        if_false: Var | Any,
        _var_type: GenericType | None = None,
        _var_data: VarData | None = None,
    ):
        """Initialize the ternary operation var.

        Args:
            condition: The condition.
            if_true: The value if the condition is true.
            if_false: The value if the condition is false.
            _var_data: Additional hooks and imports associated with the Var.
        """
        condition = (
            condition if isinstance(condition, Var) else LiteralVar.create(condition)
        )
        if_true = if_true if isinstance(if_true, Var) else LiteralVar.create(if_true)
        if_false = (
            if_false if isinstance(if_false, Var) else LiteralVar.create(if_false)
        )

        super(TernaryOperator, self).__init__(
            _var_name="",
            _var_type=_var_type or Union[if_true._var_type, if_false._var_type],
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "condition", condition)
        object.__setattr__(self, "if_true", if_true)
        object.__setattr__(self, "if_false", if_false)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self.condition)} ? {str(self.if_true)} : {str(self.if_false)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(TernaryOperator, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.condition._get_all_var_data(),
            self.if_true._get_all_var_data(),
            self.if_false._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data
