"""Collection of base classes."""

from __future__ import annotations

import dataclasses
import functools
import json
import re
import sys
from functools import cached_property
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from typing_extensions import ParamSpec

from reflex import constants
from reflex.base import Base
from reflex.constants.base import REFLEX_VAR_CLOSING_TAG, REFLEX_VAR_OPENING_TAG
from reflex.utils import serializers, types
from reflex.utils.exceptions import VarTypeError
from reflex.vars import (
    ImmutableVarData,
    Var,
    VarData,
    _decode_var_immutable,
    _extract_var_data,
    _global_vars,
)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ImmutableVar(Var):
    """Base class for immutable vars."""

    # The name of the var.
    _var_name: str = dataclasses.field()

    # The type of the var.
    _var_type: Type = dataclasses.field(default=Any)

    # Extra metadata associated with the Var
    _var_data: Optional[ImmutableVarData] = dataclasses.field(default=None)

    def __str__(self) -> str:
        """String representation of the var. Guaranteed to be a valid Javascript expression.

        Returns:
            The name of the var.
        """
        return self._var_name

    @property
    def _var_is_local(self) -> bool:
        """Whether this is a local javascript variable.

        Returns:
            False
        """
        return False

    @property
    def _var_is_string(self) -> bool:
        """Whether the var is a string literal.

        Returns:
            False
        """
        return False

    @property
    def _var_full_name_needs_state_prefix(self) -> bool:
        """Whether the full name of the var needs a _var_state prefix.

        Returns:
            False
        """
        return False

    def __post_init__(self):
        """Post-initialize the var."""
        # Decode any inline Var markup and apply it to the instance
        _var_data, _var_name = _decode_var_immutable(self._var_name)

        if _var_data or _var_name != self._var_name:
            self.__init__(
                _var_name=_var_name,
                _var_type=self._var_type,
                _var_data=ImmutableVarData.merge(self._var_data, _var_data),
            )

    def __hash__(self) -> int:
        """Define a hash function for the var.

        Returns:
            The hash of the var.
        """
        return hash((self._var_name, self._var_type, self._var_data))

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._var_data

    def _replace(self, merge_var_data=None, **kwargs: Any):
        """Make a copy of this Var with updated fields.

        Args:
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            A new ImmutableVar with the updated fields overwriting the corresponding fields in this Var.

        Raises:
            TypeError: If _var_is_local, _var_is_string, or _var_full_name_needs_state_prefix is not None.
        """
        if kwargs.get("_var_is_local", False) is not False:
            raise TypeError(
                "The _var_is_local argument is not supported for ImmutableVar."
            )

        if kwargs.get("_var_is_string", False) is not False:
            raise TypeError(
                "The _var_is_string argument is not supported for ImmutableVar."
            )

        if kwargs.get("_var_full_name_needs_state_prefix", False) is not False:
            raise TypeError(
                "The _var_full_name_needs_state_prefix argument is not supported for ImmutableVar."
            )

        field_values = dict(
            _var_name=kwargs.pop("_var_name", self._var_name),
            _var_type=kwargs.pop("_var_type", self._var_type),
            _var_data=ImmutableVarData.merge(
                kwargs.get("_var_data", self._var_data), merge_var_data
            ),
        )
        return type(self)(**field_values)

    @classmethod
    def create(
        cls,
        value: Any,
        _var_is_local: bool | None = None,
        _var_is_string: bool | None = None,
        _var_data: VarData | None = None,
    ) -> ImmutableVar | Var | None:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local. Deprecated.
            _var_is_string: Whether the var is a string literal. Deprecated.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.

        Raises:
            VarTypeError: If the value is JSON-unserializable.
            TypeError: If _var_is_local or _var_is_string is not None.
        """
        if _var_is_local is not None:
            raise TypeError(
                "The _var_is_local argument is not supported for ImmutableVar."
            )

        if _var_is_string is not None:
            raise TypeError(
                "The _var_is_string argument is not supported for ImmutableVar."
            )

        from reflex.utils import format

        # Check for none values.
        if value is None:
            return None

        # If the value is already a var, do nothing.
        if isinstance(value, Var):
            return value

        # Try to pull the imports and hooks from contained values.
        if not isinstance(value, str):
            _var_data = VarData.merge(*_extract_var_data(value), _var_data)

        # Try to serialize the value.
        type_ = type(value)
        if type_ in types.JSONType:
            name = value
        else:
            name, _serialized_type = serializers.serialize(value, get_type=True)
        if name is None:
            raise VarTypeError(
                f"No JSON serializer found for var {value} of type {type_}."
            )
        name = name if isinstance(name, str) else format.json_dumps(name)

        return cls(
            _var_name=name,
            _var_type=type_,
            _var_data=(
                ImmutableVarData(
                    state=_var_data.state,
                    imports=_var_data.imports,
                    hooks=_var_data.hooks,
                )
                if _var_data
                else None
            ),
        )

    @classmethod
    def create_safe(
        cls,
        value: Any,
        _var_is_local: bool | None = None,
        _var_is_string: bool | None = None,
        _var_data: VarData | None = None,
    ) -> Var | ImmutableVar:
        """Create a var from a value, asserting that it is not None.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local. Deprecated.
            _var_is_string: Whether the var is a string literal. Deprecated.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        var = cls.create(
            value,
            _var_is_local=_var_is_local,
            _var_is_string=_var_is_string,
            _var_data=_var_data,
        )
        assert var is not None
        return var

    def __format__(self, format_spec: str) -> str:
        """Format the var into a Javascript equivalent to an f-string.

        Args:
            format_spec: The format specifier (Ignored for now).

        Returns:
            The formatted var.
        """
        hashed_var = hash(self)

        _global_vars[hashed_var] = self

        # Encode the _var_data into the formatted output for tracking purposes.
        return f"{REFLEX_VAR_OPENING_TAG}{hashed_var}{REFLEX_VAR_CLOSING_TAG}{self._var_name}"


class StringVar(ImmutableVar):
    """Base class for immutable string vars."""


class NumberVar(ImmutableVar):
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

    def __and__(self, other: number_types | boolean_types) -> BooleanAndOperation:
        """Boolean AND two numbers.

        Args:
            other: The other number.

        Returns:
            The boolean AND operation.
        """
        boolified_other = other.bool() if isinstance(other, Var) else bool(other)
        return BooleanAndOperation(self.bool(), boolified_other)

    def __rand__(self, other: number_types | boolean_types) -> BooleanAndOperation:
        """Boolean AND two numbers.

        Args:
            other: The other number.

        Returns:
            The boolean AND operation.
        """
        boolified_other = other.bool() if isinstance(other, Var) else bool(other)
        return BooleanAndOperation(boolified_other, self.bool())

    def __or__(self, other: number_types | boolean_types) -> BooleanOrOperation:
        """Boolean OR two numbers.

        Args:
            other: The other number.

        Returns:
            The boolean OR operation.
        """
        boolified_other = other.bool() if isinstance(other, Var) else bool(other)
        return BooleanOrOperation(self.bool(), boolified_other)

    def __ror__(self, other: number_types | boolean_types) -> BooleanOrOperation:
        """Boolean OR two numbers.

        Args:
            other: The other number.

        Returns:
            The boolean OR operation.
        """
        boolified_other = other.bool() if isinstance(other, Var) else bool(other)
        return BooleanOrOperation(boolified_other, self.bool())

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

    def __lt__(self, other: number_types | boolean_types) -> LessThanOperation:
        """Less than comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        return LessThanOperation(self, +other)

    def __le__(self, other: number_types | boolean_types) -> LessThanOrEqualOperation:
        """Less than or equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        return LessThanOrEqualOperation(self, +other)

    def __eq__(self, other: number_types | boolean_types) -> EqualOperation:
        """Equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        return EqualOperation(self, +other)

    def __ne__(self, other: number_types | boolean_types) -> NotEqualOperation:
        """Not equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        return NotEqualOperation(self, +other)

    def __gt__(self, other: number_types | boolean_types) -> GreaterThanOperation:
        """Greater than comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        return GreaterThanOperation(self, +other)

    def __ge__(
        self, other: number_types | boolean_types
    ) -> GreaterThanOrEqualOperation:
        """Greater than or equal comparison.

        Args:
            other: The other number.

        Returns:
            The result of the comparison.
        """
        return GreaterThanOrEqualOperation(self, +other)

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


class BooleanVar(ImmutableVar):
    """Base class for immutable boolean vars."""

    def __and__(self, other: bool) -> BooleanAndOperation:
        """AND two booleans.

        Args:
            other: The other boolean.

        Returns:
            The boolean AND operation.
        """
        return BooleanAndOperation(self, other)

    def __rand__(self, other: bool) -> BooleanAndOperation:
        """AND two booleans.

        Args:
            other: The other boolean.

        Returns:
            The boolean AND operation.
        """
        return BooleanAndOperation(other, self)

    def __or__(self, other: bool) -> BooleanOrOperation:
        """OR two booleans.

        Args:
            other: The other boolean.

        Returns:
            The boolean OR operation.
        """
        return BooleanOrOperation(self, other)

    def __ror__(self, other: bool) -> BooleanOrOperation:
        """OR two booleans.

        Args:
            other: The other boolean.

        Returns:
            The boolean OR operation.
        """
        return BooleanOrOperation(other, self)

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
class NumberComparisonOperation(BooleanVar):
    """Base class for immutable boolean vars that are the result of a comparison operation."""

    a: number_types = dataclasses.field(default=0)
    b: number_types = dataclasses.field(default=0)

    def __init__(
        self,
        a: number_types,
        b: number_types,
        _var_data: VarData | None = None,
    ):
        """Initialize the comparison operation var.

        Args:
            a: The first value.
            b: The second value.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(NumberComparisonOperation, self).__init__(
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
        getattr(super(NumberComparisonOperation, self), name)

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


class GreaterThanOperation(NumberComparisonOperation):
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


class GreaterThanOrEqualOperation(NumberComparisonOperation):
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


class LessThanOperation(NumberComparisonOperation):
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


class LessThanOrEqualOperation(NumberComparisonOperation):
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


class EqualOperation(NumberComparisonOperation):
    """Base class for immutable boolean vars that are the result of an equal operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} == {str(second_value)})"


class NotEqualOperation(NumberComparisonOperation):
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


class BooleanAndOperation(LogicalOperation):
    """Base class for immutable boolean vars that are the result of a logical AND operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} && {str(second_value)})"


class BooleanOrOperation(LogicalOperation):
    """Base class for immutable boolean vars that are the result of a logical OR operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        first_value = self.a if isinstance(self.a, Var) else LiteralVar.create(self.a)
        second_value = self.b if isinstance(self.b, Var) else LiteralVar.create(self.b)
        return f"({str(first_value)} || {str(second_value)})"


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


class ObjectVar(ImmutableVar):
    """Base class for immutable object vars."""


class ArrayVar(ImmutableVar):
    """Base class for immutable array vars."""


class FunctionVar(ImmutableVar):
    """Base class for immutable function vars."""

    def __call__(self, *args: Var | Any) -> ArgsFunctionOperation:
        """Call the function with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The function call operation.
        """
        return ArgsFunctionOperation(
            ("...args",),
            VarOperationCall(self, *args, ImmutableVar.create_safe("...args")),
        )

    def call(self, *args: Var | Any) -> VarOperationCall:
        """Call the function with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The function call operation.
        """
        return VarOperationCall(self, *args)


class FunctionStringVar(FunctionVar):
    """Base class for immutable function vars from a string."""

    def __init__(self, func: str, _var_data: VarData | None = None) -> None:
        """Initialize the function var.

        Args:
            func: The function to call.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(FunctionVar, self).__init__(
            _var_name=func,
            _var_type=Callable,
            _var_data=ImmutableVarData.merge(_var_data),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class VarOperationCall(ImmutableVar):
    """Base class for immutable vars that are the result of a function call."""

    _func: Optional[FunctionVar] = dataclasses.field(default=None)
    _args: Tuple[Union[Var, Any], ...] = dataclasses.field(default_factory=tuple)

    def __init__(
        self, func: FunctionVar, *args: Var | Any, _var_data: VarData | None = None
    ):
        """Initialize the function call var.

        Args:
            func: The function to call.
            *args: The arguments to call the function with.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(VarOperationCall, self).__init__(
            _var_name="",
            _var_type=Any,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_func", func)
        object.__setattr__(self, "_args", args)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({str(self._func)}({', '.join([str(LiteralVar.create(arg)) for arg in self._args])}))"

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._func._get_all_var_data() if self._func is not None else None,
            *[var._get_all_var_data() for var in self._args],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __post_init__(self):
        """Post-initialize the var."""
        pass


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArgsFunctionOperation(FunctionVar):
    """Base class for immutable function defined via arguments and return expression."""

    _args_names: Tuple[str, ...] = dataclasses.field(default_factory=tuple)
    _return_expr: Union[Var, Any] = dataclasses.field(default=None)

    def __init__(
        self,
        args_names: Tuple[str, ...],
        return_expr: Var | Any,
        _var_data: VarData | None = None,
    ) -> None:
        """Initialize the function with arguments var.

        Args:
            args_names: The names of the arguments.
            return_expr: The return expression of the function.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ArgsFunctionOperation, self).__init__(
            _var_name=f"",
            _var_type=Callable,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_args_names", args_names)
        object.__setattr__(self, "_return_expr", return_expr)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"(({', '.join(self._args_names)}) => ({str(LiteralVar.create(self._return_expr))}))"

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._return_expr._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __post_init__(self):
        """Post-initialize the var."""


class LiteralVar(ImmutableVar):
    """Base class for immutable literal vars."""

    @classmethod
    def create(
        cls,
        value: Any,
        _var_data: VarData | None = None,
    ) -> Var:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.

        Raises:
            TypeError: If the value is not a supported type for LiteralVar.
        """
        if isinstance(value, Var):
            if _var_data is None:
                return value
            return value._replace(merge_var_data=_var_data)

        if value is None:
            return ImmutableVar.create_safe("null", _var_data=_var_data)

        if isinstance(value, Base):
            return LiteralObjectVar(
                value.dict(), _var_type=type(value), _var_data=_var_data
            )

        if isinstance(value, str):
            return LiteralStringVar.create(value, _var_data=_var_data)

        constructor = type_mapping.get(type(value))

        if constructor is None:
            raise TypeError(f"Unsupported type {type(value)} for LiteralVar.")

        return constructor(value, _var_data=_var_data)

    def __post_init__(self):
        """Post-initialize the var."""


# Compile regex for finding reflex var tags.
_decode_var_pattern_re = (
    rf"{constants.REFLEX_VAR_OPENING_TAG}(.*?){constants.REFLEX_VAR_CLOSING_TAG}"
)
_decode_var_pattern = re.compile(_decode_var_pattern_re, flags=re.DOTALL)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralStringVar(LiteralVar):
    """Base class for immutable literal string vars."""

    _var_value: str = dataclasses.field(default="")

    def __init__(
        self,
        _var_value: str,
        _var_data: VarData | None = None,
    ):
        """Initialize the string var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralStringVar, self).__init__(
            _var_name=f'"{_var_value}"',
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "_var_value", _var_value)

    @classmethod
    def create(
        cls,
        value: str,
        _var_data: VarData | None = None,
    ) -> LiteralStringVar | ConcatVarOperation:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        if REFLEX_VAR_OPENING_TAG in value:
            strings_and_vals: list[Var | str] = []
            offset = 0

            # Initialize some methods for reading json.
            var_data_config = VarData().__config__

            def json_loads(s):
                try:
                    return var_data_config.json_loads(s)
                except json.decoder.JSONDecodeError:
                    return var_data_config.json_loads(
                        var_data_config.json_loads(f'"{s}"')
                    )

            # Find all tags
            while m := _decode_var_pattern.search(value):
                start, end = m.span()
                if start > 0:
                    strings_and_vals.append(value[:start])

                serialized_data = m.group(1)

                if serialized_data.isnumeric() or (
                    serialized_data[0] == "-" and serialized_data[1:].isnumeric()
                ):
                    # This is a global immutable var.
                    var = _global_vars[int(serialized_data)]
                    strings_and_vals.append(var)
                    value = value[(end + len(var._var_name)) :]
                else:
                    data = json_loads(serialized_data)
                    string_length = data.pop("string_length", None)
                    var_data = VarData.parse_obj(data)

                    # Use string length to compute positions of interpolations.
                    if string_length is not None:
                        realstart = start + offset
                        var_data.interpolations = [
                            (realstart, realstart + string_length)
                        ]
                        strings_and_vals.append(
                            ImmutableVar.create_safe(
                                value[end : (end + string_length)], _var_data=var_data
                            )
                        )
                        value = value[(end + string_length) :]

                offset += end - start

            if value:
                strings_and_vals.append(value)

            return ConcatVarOperation(*strings_and_vals, _var_data=_var_data)

        return LiteralStringVar(
            value,
            _var_data=_var_data,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ConcatVarOperation(StringVar):
    """Representing a concatenation of literal string vars."""

    _var_value: Tuple[Union[Var, str], ...] = dataclasses.field(default_factory=tuple)

    def __init__(self, *value: Var | str, _var_data: VarData | None = None):
        """Initialize the operation of concatenating literal string vars.

        Args:
            value: The values to concatenate.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ConcatVarOperation, self).__init__(
            _var_name="", _var_data=ImmutableVarData.merge(_var_data), _var_type=str
        )
        object.__setattr__(self, "_var_value", value)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "("
            + "+".join(
                [
                    str(element) if isinstance(element, Var) else f'"{element}"'
                    for element in self._var_value
                ]
            )
            + ")"
        )

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            *[
                var._get_all_var_data()
                for var in self._var_value
                if isinstance(var, Var)
            ],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __post_init__(self):
        """Post-initialize the var."""
        pass


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
        return hash(self._var_value)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralObjectVar(LiteralVar):
    """Base class for immutable literal object vars."""

    _var_value: Dict[Union[Var, Any], Union[Var, Any]] = dataclasses.field(
        default_factory=dict
    )

    def __init__(
        self,
        _var_value: dict[Var | Any, Var | Any],
        _var_type: Type = dict,
        _var_data: VarData | None = None,
    ):
        """Initialize the object var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralObjectVar, self).__init__(
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self,
            "_var_value",
            _var_value,
        )
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "{ "
            + ", ".join(
                [
                    f"[{str(LiteralVar.create(key))}] : {str(LiteralVar.create(value))}"
                    for key, value in self._var_value.items()
                ]
            )
            + " }"
        )

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            *[
                value._get_all_var_data()
                for key, value in self._var_value
                if isinstance(value, Var)
            ],
            *[
                key._get_all_var_data()
                for key, value in self._var_value
                if isinstance(key, Var)
            ],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralArrayVar(LiteralVar):
    """Base class for immutable literal array vars."""

    _var_value: Union[
        List[Union[Var, Any]], Set[Union[Var, Any]], Tuple[Union[Var, Any], ...]
    ] = dataclasses.field(default_factory=list)

    def __init__(
        self,
        _var_value: list[Var | Any] | tuple[Var | Any] | set[Var | Any],
        _var_data: VarData | None = None,
    ):
        """Initialize the array var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralArrayVar, self).__init__(
            _var_name="",
            _var_data=ImmutableVarData.merge(_var_data),
            _var_type=list,
        )
        object.__setattr__(self, "_var_value", _var_value)
        object.__delattr__(self, "_var_name")

    def __getattr__(self, name):
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "["
            + ", ".join(
                [str(LiteralVar.create(element)) for element in self._var_value]
            )
            + "]"
        )

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            *[
                var._get_all_var_data()
                for var in self._var_value
                if isinstance(var, Var)
            ],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data


P = ParamSpec("P")
T = TypeVar("T", bound=ImmutableVar)


def var_operation(*, output: Type[T]) -> Callable[[Callable[P, str]], Callable[P, T]]:
    """Decorator for creating a var operation.

    Example:
    ```python
    @var_operation(output=NumberVar)
    def add(a: NumberVar | int | float, b: NumberVar | int | float):
        return f"({a} + {b})"
    ```

    Args:
        output: The output type of the operation.

    Returns:
        The decorator.
    """

    def decorator(func: Callable[P, str], output=output):
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return output(
                _var_name=func(*args, **kwargs),
                _var_data=VarData.merge(
                    *[arg._get_all_var_data() for arg in args if isinstance(arg, Var)],
                    *[
                        arg._get_all_var_data()
                        for arg in kwargs.values()
                        if isinstance(arg, Var)
                    ],
                ),
            )

        return wrapper

    return decorator


type_mapping = {
    int: LiteralNumberVar,
    float: LiteralNumberVar,
    bool: LiteralBooleanVar,
    dict: LiteralObjectVar,
    list: LiteralArrayVar,
    tuple: LiteralArrayVar,
    set: LiteralArrayVar,
}

number_types = Union[NumberVar, LiteralNumberVar, int, float]
boolean_types = Union[BooleanVar, LiteralBooleanVar, bool]
