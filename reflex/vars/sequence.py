"""Collection of string classes and utilities."""

from __future__ import annotations

import collections.abc
import dataclasses
import decimal
import inspect
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, TypeVar, get_args, overload

from typing_extensions import TypeVar as TypingExtensionsTypeVar

from reflex import constants
from reflex.constants.base import REFLEX_VAR_OPENING_TAG
from reflex.constants.colors import Color
from reflex.utils import types
from reflex.utils.exceptions import VarTypeError
from reflex.utils.types import GenericType, get_origin

from .base import (
    CachedVarOperation,
    CustomVarOperationReturn,
    LiteralVar,
    Var,
    VarData,
    _global_vars,
    cached_property_no_lock,
    figure_out_type,
    get_python_literal,
    get_unique_variable_name,
    unionize,
    var_operation,
    var_operation_return,
)
from .number import (
    BooleanVar,
    LiteralNumberVar,
    NumberVar,
    raise_unsupported_operand_types,
    ternary_operation,
)

if TYPE_CHECKING:
    from .base import BASE_TYPE, DATACLASS_TYPE, SQLA_TYPE
    from .function import FunctionVar
    from .object import ObjectVar

ARRAY_VAR_TYPE = TypeVar("ARRAY_VAR_TYPE", bound=Sequence, covariant=True)
OTHER_ARRAY_VAR_TYPE = TypeVar("OTHER_ARRAY_VAR_TYPE", bound=Sequence, covariant=True)
MAPPING_VAR_TYPE = TypeVar("MAPPING_VAR_TYPE", bound=Mapping, covariant=True)

OTHER_TUPLE = TypeVar("OTHER_TUPLE")

INNER_ARRAY_VAR = TypeVar("INNER_ARRAY_VAR")


KEY_TYPE = TypeVar("KEY_TYPE")
VALUE_TYPE = TypeVar("VALUE_TYPE")


class ArrayVar(Var[ARRAY_VAR_TYPE], python_types=(Sequence, set)):
    """Base class for immutable array vars."""

    def join(self, sep: StringVar | str = "") -> StringVar:
        """Join the elements of the array.

        Args:
            sep: The separator between elements.

        Returns:
            The joined elements.
        """
        if not isinstance(sep, (StringVar, str)):
            raise_unsupported_operand_types("join", (type(self), type(sep)))
        if (
            isinstance(self, LiteralArrayVar)
            and (
                len(
                    args := [
                        x
                        for x in self._var_value
                        if isinstance(x, (LiteralStringVar, str))
                    ]
                )
                == len(self._var_value)
            )
            and isinstance(sep, (LiteralStringVar, str))
        ):
            sep_str = sep._var_value if isinstance(sep, LiteralStringVar) else sep
            return LiteralStringVar.create(
                sep_str.join(
                    i._var_value if isinstance(i, LiteralStringVar) else i for i in args
                )
            )
        return array_join_operation(self, sep)

    def reverse(self) -> ArrayVar[ARRAY_VAR_TYPE]:
        """Reverse the array.

        Returns:
            The reversed array.
        """
        return array_reverse_operation(self)

    def __add__(self, other: ArrayVar[ARRAY_VAR_TYPE]) -> ArrayVar[ARRAY_VAR_TYPE]:
        """Concatenate two arrays.

        Parameters:
            other: The other array to concatenate.

        Returns:
            ArrayConcatOperation: The concatenation of the two arrays.
        """
        if not isinstance(other, ArrayVar):
            raise_unsupported_operand_types("+", (type(self), type(other)))

        return array_concat_operation(self, other)

    @overload
    def __getitem__(self, i: slice) -> ArrayVar[ARRAY_VAR_TYPE]: ...

    @overload
    def __getitem__(
        self: (
            ArrayVar[tuple[int, OTHER_TUPLE]]
            | ArrayVar[tuple[float, OTHER_TUPLE]]
            | ArrayVar[tuple[int | float, OTHER_TUPLE]]
        ),
        i: Literal[0, -2],
    ) -> NumberVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[tuple[Any, bool]], i: Literal[1, -1]
    ) -> BooleanVar: ...

    @overload
    def __getitem__(
        self: (
            ArrayVar[tuple[Any, int]]
            | ArrayVar[tuple[Any, float]]
            | ArrayVar[tuple[Any, int | float]]
        ),
        i: Literal[1, -1],
    ) -> NumberVar: ...

    @overload
    def __getitem__(  # pyright: ignore [reportOverlappingOverload]
        self: ArrayVar[tuple[str, Any]], i: Literal[0, -2]
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[tuple[Any, str]], i: Literal[1, -1]
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[tuple[bool, Any]], i: Literal[0, -2]
    ) -> BooleanVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[Sequence[bool]], i: int | NumberVar
    ) -> BooleanVar: ...

    @overload
    def __getitem__(
        self: (
            ArrayVar[Sequence[int]]
            | ArrayVar[Sequence[float]]
            | ArrayVar[Sequence[int | float]]
        ),
        i: int | NumberVar,
    ) -> NumberVar: ...

    @overload
    def __getitem__(self: ArrayVar[Sequence[str]], i: int | NumberVar) -> StringVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[Sequence[OTHER_ARRAY_VAR_TYPE]],
        i: int | NumberVar,
    ) -> ArrayVar[OTHER_ARRAY_VAR_TYPE]: ...

    @overload
    def __getitem__(
        self: ArrayVar[Sequence[MAPPING_VAR_TYPE]],
        i: int | NumberVar,
    ) -> ObjectVar[MAPPING_VAR_TYPE]: ...

    @overload
    def __getitem__(
        self: ArrayVar[Sequence[BASE_TYPE]],
        i: int | NumberVar,
    ) -> ObjectVar[BASE_TYPE]: ...

    @overload
    def __getitem__(
        self: ArrayVar[Sequence[SQLA_TYPE]],
        i: int | NumberVar,
    ) -> ObjectVar[SQLA_TYPE]: ...

    @overload
    def __getitem__(
        self: ArrayVar[Sequence[DATACLASS_TYPE]],
        i: int | NumberVar,
    ) -> ObjectVar[DATACLASS_TYPE]: ...

    @overload
    def __getitem__(self, i: int | NumberVar) -> Var: ...

    def __getitem__(self, i: Any) -> ArrayVar[ARRAY_VAR_TYPE] | Var:
        """Get a slice of the array.

        Args:
            i: The slice.

        Returns:
            The array slice operation.
        """
        if isinstance(i, slice):
            return ArraySliceOperation.create(self, i)
        if not isinstance(i, (int, NumberVar)) or (
            isinstance(i, NumberVar) and i._is_strict_float()
        ):
            raise_unsupported_operand_types("[]", (type(self), type(i)))
        return array_item_operation(self, i)

    def length(self) -> NumberVar[int]:
        """Get the length of the array.

        Returns:
            The length of the array.
        """
        return array_length_operation(self)

    @overload
    @classmethod
    def range(cls, stop: int | NumberVar, /) -> ArrayVar[list[int]]: ...

    @overload
    @classmethod
    def range(
        cls,
        start: int | NumberVar,
        end: int | NumberVar,
        step: int | NumberVar = 1,
        /,
    ) -> ArrayVar[list[int]]: ...

    @overload
    @classmethod
    def range(
        cls,
        first_endpoint: int | NumberVar,
        second_endpoint: int | NumberVar | None = None,
        step: int | NumberVar | None = None,
    ) -> ArrayVar[list[int]]: ...

    @classmethod
    def range(
        cls,
        first_endpoint: int | NumberVar,
        second_endpoint: int | NumberVar | None = None,
        step: int | NumberVar | None = None,
    ) -> ArrayVar[list[int]]:
        """Create a range of numbers.

        Args:
            first_endpoint: The end of the range if second_endpoint is not provided, otherwise the start of the range.
            second_endpoint: The end of the range.
            step: The step of the range.

        Returns:
            The range of numbers.
        """
        if any(
            not isinstance(i, (int, NumberVar))
            for i in (first_endpoint, second_endpoint, step)
            if i is not None
        ):
            raise_unsupported_operand_types(
                "range", (type(first_endpoint), type(second_endpoint), type(step))
            )
        if second_endpoint is None:
            start = 0
            end = first_endpoint
        else:
            start = first_endpoint
            end = second_endpoint

        return array_range_operation(start, end, step or 1)

    @overload
    def contains(self, other: Any) -> BooleanVar: ...

    @overload
    def contains(self, other: Any, field: StringVar | str) -> BooleanVar: ...

    def contains(self, other: Any, field: Any = None) -> BooleanVar:
        """Check if the array contains an element.

        Args:
            other: The element to check for.
            field: The field to check.

        Returns:
            The array contains operation.
        """
        if field is not None:
            if not isinstance(field, (StringVar, str)):
                raise_unsupported_operand_types("contains", (type(self), type(field)))
            return array_contains_field_operation(self, other, field)
        return array_contains_operation(self, other)

    def pluck(self, field: StringVar | str) -> ArrayVar:
        """Pluck a field from the array.

        Args:
            field: The field to pluck from the array.

        Returns:
            The array pluck operation.
        """
        return array_pluck_operation(self, field)

    def __mul__(self, other: NumberVar | int) -> ArrayVar[ARRAY_VAR_TYPE]:
        """Multiply the sequence by a number or integer.

        Parameters:
            other: The number or integer to multiply the sequence by.

        Returns:
            ArrayVar[ARRAY_VAR_TYPE]: The result of multiplying the sequence by the given number or integer.
        """
        if not isinstance(other, (NumberVar, int)) or (
            isinstance(other, NumberVar) and other._is_strict_float()
        ):
            raise_unsupported_operand_types("*", (type(self), type(other)))

        return repeat_array_operation(self, other)

    __rmul__ = __mul__

    @overload
    def __lt__(self, other: ArrayVar[ARRAY_VAR_TYPE]) -> BooleanVar: ...

    @overload
    def __lt__(self, other: list | tuple) -> BooleanVar: ...

    def __lt__(self, other: Any):
        """Check if the array is less than another array.

        Args:
            other: The other array.

        Returns:
            The array less than operation.
        """
        if not isinstance(other, (ArrayVar, list, tuple)):
            raise_unsupported_operand_types("<", (type(self), type(other)))

        return array_lt_operation(self, other)

    @overload
    def __gt__(self, other: ArrayVar[ARRAY_VAR_TYPE]) -> BooleanVar: ...

    @overload
    def __gt__(self, other: list | tuple) -> BooleanVar: ...

    def __gt__(self, other: Any):
        """Check if the array is greater than another array.

        Args:
            other: The other array.

        Returns:
            The array greater than operation.
        """
        if not isinstance(other, (ArrayVar, list, tuple)):
            raise_unsupported_operand_types(">", (type(self), type(other)))

        return array_gt_operation(self, other)

    @overload
    def __le__(self, other: ArrayVar[ARRAY_VAR_TYPE]) -> BooleanVar: ...

    @overload
    def __le__(self, other: list | tuple) -> BooleanVar: ...

    def __le__(self, other: Any):
        """Check if the array is less than or equal to another array.

        Args:
            other: The other array.

        Returns:
            The array less than or equal operation.
        """
        if not isinstance(other, (ArrayVar, list, tuple)):
            raise_unsupported_operand_types("<=", (type(self), type(other)))

        return array_le_operation(self, other)

    @overload
    def __ge__(self, other: ArrayVar[ARRAY_VAR_TYPE]) -> BooleanVar: ...

    @overload
    def __ge__(self, other: list | tuple) -> BooleanVar: ...

    def __ge__(self, other: Any):
        """Check if the array is greater than or equal to another array.

        Args:
            other: The other array.

        Returns:
            The array greater than or equal operation.
        """
        if not isinstance(other, (ArrayVar, list, tuple)):
            raise_unsupported_operand_types(">=", (type(self), type(other)))

        return array_ge_operation(self, other)

    def foreach(self, fn: Any):
        """Apply a function to each element of the array.

        Args:
            fn: The function to apply.

        Returns:
            The array after applying the function.

        Raises:
            VarTypeError: If the function takes more than one argument.
        """
        from .function import ArgsFunctionOperation

        if not callable(fn):
            raise_unsupported_operand_types("foreach", (type(self), type(fn)))
        # get the number of arguments of the function
        num_args = len(inspect.signature(fn).parameters)
        if num_args > 1:
            msg = "The function passed to foreach should take at most one argument."
            raise VarTypeError(msg)

        if num_args == 0:
            return_value = fn()
            function_var = ArgsFunctionOperation.create((), return_value)
        else:
            # generic number var
            number_var = Var("").to(NumberVar, int)

            first_arg_type = self[number_var]._var_type

            arg_name = get_unique_variable_name()

            # get first argument type
            first_arg = Var(
                _js_expr=arg_name,
                _var_type=first_arg_type,
            ).guess_type()

            function_var = ArgsFunctionOperation.create(
                (arg_name,),
                Var.create(fn(first_arg)),
            )

        return map_array_operation(self, function_var)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralArrayVar(CachedVarOperation, LiteralVar, ArrayVar[ARRAY_VAR_TYPE]):
    """Base class for immutable literal array vars."""

    _var_value: Sequence[Var | Any] = dataclasses.field(default=())

    @cached_property_no_lock
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

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the VarData associated with the Var.

        Returns:
            The VarData associated with the Var.
        """
        return VarData.merge(
            *[
                LiteralVar.create(element)._get_all_var_data()
                for element in self._var_value
            ],
            self._var_data,
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((self.__class__.__name__, self._js_expr))

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.

        Raises:
            TypeError: If the array elements are not of type LiteralVar.
        """
        elements = []
        for element in self._var_value:
            element_var = LiteralVar.create(element)
            if not isinstance(element_var, LiteralVar):
                msg = f"Array elements must be of type LiteralVar, not {type(element_var)}"
                raise TypeError(msg)
            elements.append(element_var.json())

        return "[" + ", ".join(elements) + "]"

    @classmethod
    def create(
        cls,
        value: OTHER_ARRAY_VAR_TYPE,
        _var_type: type[OTHER_ARRAY_VAR_TYPE] | None = None,
        _var_data: VarData | None = None,
    ) -> LiteralArrayVar[OTHER_ARRAY_VAR_TYPE]:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return LiteralArrayVar(
            _js_expr="",
            _var_type=figure_out_type(value) if _var_type is None else _var_type,
            _var_data=_var_data,
            _var_value=value,
        )


STRING_TYPE = TypingExtensionsTypeVar("STRING_TYPE", default=str)


class StringVar(Var[STRING_TYPE], python_types=str):
    """Base class for immutable string vars."""

    def __add__(self, other: StringVar | str) -> ConcatVarOperation:
        """Concatenate two strings.

        Args:
            other: The other string.

        Returns:
            The string concatenation operation.
        """
        if not isinstance(other, (StringVar, str)):
            raise_unsupported_operand_types("+", (type(self), type(other)))

        return ConcatVarOperation.create(self, other)

    def __radd__(self, other: StringVar | str) -> ConcatVarOperation:
        """Concatenate two strings.

        Args:
            other: The other string.

        Returns:
            The string concatenation operation.
        """
        if not isinstance(other, (StringVar, str)):
            raise_unsupported_operand_types("+", (type(other), type(self)))

        return ConcatVarOperation.create(other, self)

    def __mul__(self, other: NumberVar | int) -> StringVar:
        """Multiply the sequence by a number or an integer.

        Args:
            other: The number or integer to multiply the sequence by.

        Returns:
            StringVar: The resulting sequence after multiplication.
        """
        if not isinstance(other, (NumberVar, int)):
            raise_unsupported_operand_types("*", (type(self), type(other)))

        return (self.split() * other).join()

    def __rmul__(self, other: NumberVar | int) -> StringVar:
        """Multiply the sequence by a number or an integer.

        Args:
            other: The number or integer to multiply the sequence by.

        Returns:
            StringVar: The resulting sequence after multiplication.
        """
        if not isinstance(other, (NumberVar, int)):
            raise_unsupported_operand_types("*", (type(other), type(self)))

        return (self.split() * other).join()

    @overload
    def __getitem__(self, i: slice) -> StringVar: ...

    @overload
    def __getitem__(self, i: int | NumberVar) -> StringVar: ...

    def __getitem__(self, i: Any) -> StringVar:
        """Get a slice of the string.

        Args:
            i: The slice.

        Returns:
            The string slice operation.
        """
        if isinstance(i, slice):
            return self.split()[i].join()
        if not isinstance(i, (int, NumberVar)) or (
            isinstance(i, NumberVar) and i._is_strict_float()
        ):
            raise_unsupported_operand_types("[]", (type(self), type(i)))
        return string_item_operation(self, i)

    def length(self) -> NumberVar:
        """Get the length of the string.

        Returns:
            The string length operation.
        """
        return self.split().length()

    def lower(self) -> StringVar:
        """Convert the string to lowercase.

        Returns:
            The string lower operation.
        """
        return string_lower_operation(self)

    def upper(self) -> StringVar:
        """Convert the string to uppercase.

        Returns:
            The string upper operation.
        """
        return string_upper_operation(self)

    def title(self) -> StringVar:
        """Convert the string to title case.

        Returns:
            The string title operation.
        """
        return string_title_operation(self)

    def capitalize(self) -> StringVar:
        """Capitalize the string.

        Returns:
            The string capitalize operation.
        """
        return string_capitalize_operation(self)

    def strip(self) -> StringVar:
        """Strip the string.

        Returns:
            The string strip operation.
        """
        return string_strip_operation(self)

    def reversed(self) -> StringVar:
        """Reverse the string.

        Returns:
            The string reverse operation.
        """
        return self.split().reverse().join()

    def contains(
        self, other: StringVar | str, field: StringVar | str | None = None
    ) -> BooleanVar:
        """Check if the string contains another string.

        Args:
            other: The other string.
            field: The field to check.

        Returns:
            The string contains operation.
        """
        if not isinstance(other, (StringVar, str)):
            raise_unsupported_operand_types("contains", (type(self), type(other)))
        if field is not None:
            if not isinstance(field, (StringVar, str)):
                raise_unsupported_operand_types("contains", (type(self), type(field)))
            return string_contains_field_operation(self, other, field)
        return string_contains_operation(self, other)

    def split(self, separator: StringVar | str = "") -> ArrayVar[list[str]]:
        """Split the string.

        Args:
            separator: The separator.

        Returns:
            The string split operation.
        """
        if not isinstance(separator, (StringVar, str)):
            raise_unsupported_operand_types("split", (type(self), type(separator)))
        return string_split_operation(self, separator)

    def startswith(self, prefix: StringVar | str) -> BooleanVar:
        """Check if the string starts with a prefix.

        Args:
            prefix: The prefix.

        Returns:
            The string starts with operation.
        """
        if not isinstance(prefix, (StringVar, str)):
            raise_unsupported_operand_types("startswith", (type(self), type(prefix)))
        return string_starts_with_operation(self, prefix)

    def endswith(self, suffix: StringVar | str) -> BooleanVar:
        """Check if the string ends with a suffix.

        Args:
            suffix: The suffix.

        Returns:
            The string ends with operation.
        """
        if not isinstance(suffix, (StringVar, str)):
            raise_unsupported_operand_types("endswith", (type(self), type(suffix)))
        return string_ends_with_operation(self, suffix)

    def __lt__(self, other: StringVar | str) -> BooleanVar:
        """Check if the string is less than another string.

        Args:
            other: The other string.

        Returns:
            The string less than operation.
        """
        if not isinstance(other, (StringVar, str)):
            raise_unsupported_operand_types("<", (type(self), type(other)))

        return string_lt_operation(self, other)

    def __gt__(self, other: StringVar | str) -> BooleanVar:
        """Check if the string is greater than another string.

        Args:
            other: The other string.

        Returns:
            The string greater than operation.
        """
        if not isinstance(other, (StringVar, str)):
            raise_unsupported_operand_types(">", (type(self), type(other)))

        return string_gt_operation(self, other)

    def __le__(self, other: StringVar | str) -> BooleanVar:
        """Check if the string is less than or equal to another string.

        Args:
            other: The other string.

        Returns:
            The string less than or equal operation.
        """
        if not isinstance(other, (StringVar, str)):
            raise_unsupported_operand_types("<=", (type(self), type(other)))

        return string_le_operation(self, other)

    def __ge__(self, other: StringVar | str) -> BooleanVar:
        """Check if the string is greater than or equal to another string.

        Args:
            other: The other string.

        Returns:
            The string greater than or equal operation.
        """
        if not isinstance(other, (StringVar, str)):
            raise_unsupported_operand_types(">=", (type(self), type(other)))

        return string_ge_operation(self, other)

    @overload
    def replace(  # pyright: ignore [reportOverlappingOverload]
        self, search_value: StringVar | str, new_value: StringVar | str
    ) -> StringVar: ...

    @overload
    def replace(
        self, search_value: Any, new_value: Any
    ) -> CustomVarOperationReturn[StringVar]: ...

    def replace(self, search_value: Any, new_value: Any) -> StringVar:  # pyright: ignore [reportInconsistentOverload]
        """Replace a string with a value.

        Args:
            search_value: The string to search.
            new_value: The value to be replaced with.

        Returns:
            The string replace operation.
        """
        if not isinstance(search_value, (StringVar, str)):
            raise_unsupported_operand_types("replace", (type(self), type(search_value)))
        if not isinstance(new_value, (StringVar, str)):
            raise_unsupported_operand_types("replace", (type(self), type(new_value)))

        return string_replace_operation(self, search_value, new_value)


@var_operation
def string_lt_operation(lhs: StringVar[Any] | str, rhs: StringVar[Any] | str):
    """Check if a string is less than another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string less than operation.
    """
    return var_operation_return(js_expression=f"{lhs} < {rhs}", var_type=bool)


@var_operation
def string_gt_operation(lhs: StringVar[Any] | str, rhs: StringVar[Any] | str):
    """Check if a string is greater than another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string greater than operation.
    """
    return var_operation_return(js_expression=f"{lhs} > {rhs}", var_type=bool)


@var_operation
def string_le_operation(lhs: StringVar[Any] | str, rhs: StringVar[Any] | str):
    """Check if a string is less than or equal to another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string less than or equal operation.
    """
    return var_operation_return(js_expression=f"{lhs} <= {rhs}", var_type=bool)


@var_operation
def string_ge_operation(lhs: StringVar[Any] | str, rhs: StringVar[Any] | str):
    """Check if a string is greater than or equal to another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string greater than or equal operation.
    """
    return var_operation_return(js_expression=f"{lhs} >= {rhs}", var_type=bool)


@var_operation
def string_lower_operation(string: StringVar[Any]):
    """Convert a string to lowercase.

    Args:
        string: The string to convert.

    Returns:
        The lowercase string.
    """
    return var_operation_return(js_expression=f"{string}.toLowerCase()", var_type=str)


@var_operation
def string_upper_operation(string: StringVar[Any]):
    """Convert a string to uppercase.

    Args:
        string: The string to convert.

    Returns:
        The uppercase string.
    """
    return var_operation_return(js_expression=f"{string}.toUpperCase()", var_type=str)


@var_operation
def string_title_operation(string: StringVar[Any]):
    """Convert a string to title case.

    Args:
        string: The string to convert.

    Returns:
        The title case string.
    """
    return var_operation_return(
        js_expression=f"{string}.split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()).join(' ')",
        var_type=str,
    )


@var_operation
def string_capitalize_operation(string: StringVar[Any]):
    """Capitalize a string.

    Args:
        string: The string to capitalize.

    Returns:
        The capitalized string.
    """
    return var_operation_return(
        js_expression=f"(((s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase())({string}))",
        var_type=str,
    )


@var_operation
def string_strip_operation(string: StringVar[Any]):
    """Strip a string.

    Args:
        string: The string to strip.

    Returns:
        The stripped string.
    """
    return var_operation_return(js_expression=f"{string}.trim()", var_type=str)


@var_operation
def string_contains_field_operation(
    haystack: StringVar[Any], needle: StringVar[Any] | str, field: StringVar[Any] | str
):
    """Check if a string contains another string.

    Args:
        haystack: The haystack.
        needle: The needle.
        field: The field to check.

    Returns:
        The string contains operation.
    """
    return var_operation_return(
        js_expression=f"{haystack}.some(obj => obj[{field}] === {needle})",
        var_type=bool,
    )


@var_operation
def string_contains_operation(haystack: StringVar[Any], needle: StringVar[Any] | str):
    """Check if a string contains another string.

    Args:
        haystack: The haystack.
        needle: The needle.

    Returns:
        The string contains operation.
    """
    return var_operation_return(
        js_expression=f"{haystack}.includes({needle})", var_type=bool
    )


@var_operation
def string_starts_with_operation(
    full_string: StringVar[Any], prefix: StringVar[Any] | str
):
    """Check if a string starts with a prefix.

    Args:
        full_string: The full string.
        prefix: The prefix.

    Returns:
        Whether the string starts with the prefix.
    """
    return var_operation_return(
        js_expression=f"{full_string}.startsWith({prefix})", var_type=bool
    )


@var_operation
def string_ends_with_operation(
    full_string: StringVar[Any], suffix: StringVar[Any] | str
):
    """Check if a string ends with a suffix.

    Args:
        full_string: The full string.
        suffix: The suffix.

    Returns:
        Whether the string ends with the suffix.
    """
    return var_operation_return(
        js_expression=f"{full_string}.endsWith({suffix})", var_type=bool
    )


@var_operation
def string_item_operation(string: StringVar[Any], index: NumberVar | int):
    """Get an item from a string.

    Args:
        string: The string.
        index: The index of the item.

    Returns:
        The item from the string.
    """
    return var_operation_return(js_expression=f"{string}.at({index})", var_type=str)


@var_operation
def array_join_operation(array: ArrayVar, sep: StringVar[Any] | str = ""):
    """Join the elements of an array.

    Args:
        array: The array.
        sep: The separator.

    Returns:
        The joined elements.
    """
    return var_operation_return(js_expression=f"{array}.join({sep})", var_type=str)


@var_operation
def string_replace_operation(
    string: StringVar[Any], search_value: StringVar | str, new_value: StringVar | str
):
    """Replace a string with a value.

    Args:
        string: The string.
        search_value: The string to search.
        new_value: The value to be replaced with.

    Returns:
        The string replace operation.
    """
    return var_operation_return(
        js_expression=f"{string}.replaceAll({search_value}, {new_value})",
        var_type=str,
    )


@var_operation
def get_decimal_string_separator_operation(value: NumberVar, separator: StringVar):
    """Get the decimal string separator.

    Args:
        value: The number.
        separator: The separator.

    Returns:
        The decimal string separator.
    """
    return var_operation_return(
        js_expression=f"({value}.toLocaleString('en-US').replaceAll(',', {separator}))",
        var_type=str,
    )


@var_operation
def get_decimal_string_operation(
    value: NumberVar, decimals: NumberVar, separator: StringVar
):
    """Get the decimal string of the number.

    Args:
        value: The number.
        decimals: The number of decimals.
        separator: The separator.

    Returns:
        The decimal string of the number.
    """
    return var_operation_return(
        js_expression=f"({value}.toLocaleString('en-US', ((decimals) => ({{minimumFractionDigits: decimals, maximumFractionDigits: decimals}}))({decimals})).replaceAll(',', {separator}))",
        var_type=str,
    )


# Compile regex for finding reflex var tags.
_decode_var_pattern_re = (
    rf"{constants.REFLEX_VAR_OPENING_TAG}(.*?){constants.REFLEX_VAR_CLOSING_TAG}"
)
_decode_var_pattern = re.compile(_decode_var_pattern_re, flags=re.DOTALL)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralStringVar(LiteralVar, StringVar[str]):
    """Base class for immutable literal string vars."""

    _var_value: str = dataclasses.field(default="")

    @classmethod
    def create(
        cls,
        value: str,
        _var_type: GenericType | None = None,
        _var_data: VarData | None = None,
    ) -> StringVar:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        # Determine var type in case the value is inherited from str.
        _var_type = _var_type or type(value) or str

        if REFLEX_VAR_OPENING_TAG in value:
            strings_and_vals: list[Var | str] = []
            offset = 0

            # Find all tags
            while m := _decode_var_pattern.search(value):
                start, end = m.span()

                strings_and_vals.append(value[:start])

                serialized_data = m.group(1)

                if serialized_data.isnumeric() or (
                    serialized_data[0] == "-" and serialized_data[1:].isnumeric()
                ):
                    # This is a global immutable var.
                    var = _global_vars[int(serialized_data)]
                    strings_and_vals.append(var)
                    value = value[(end + len(var._js_expr)) :]

                offset += end - start

            strings_and_vals.append(value)

            filtered_strings_and_vals = [
                s for s in strings_and_vals if isinstance(s, Var) or s
            ]
            if len(filtered_strings_and_vals) == 1:
                only_string = filtered_strings_and_vals[0]
                if isinstance(only_string, str):
                    return LiteralVar.create(only_string).to(StringVar, _var_type)
                return only_string.to(StringVar, only_string._var_type)

            if len(
                literal_strings := [
                    s
                    for s in filtered_strings_and_vals
                    if isinstance(s, (str, LiteralStringVar))
                ]
            ) == len(filtered_strings_and_vals):
                return LiteralStringVar.create(
                    "".join(
                        s._var_value if isinstance(s, LiteralStringVar) else s
                        for s in literal_strings
                    ),
                    _var_type=_var_type,
                    _var_data=VarData.merge(
                        _var_data,
                        *(
                            s._get_all_var_data()
                            for s in filtered_strings_and_vals
                            if isinstance(s, Var)
                        ),
                    ),
                )

            concat_result = ConcatVarOperation.create(
                *filtered_strings_and_vals,
                _var_data=_var_data,
            )

            return (
                concat_result
                if _var_type is str
                else concat_result.to(StringVar, _var_type)
            )

        return LiteralStringVar(
            _js_expr=json.dumps(value),
            _var_type=_var_type,
            _var_data=_var_data,
            _var_value=value,
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((type(self).__name__, self._var_value))

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return json.dumps(self._var_value)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ConcatVarOperation(CachedVarOperation, StringVar[str]):
    """Representing a concatenation of literal string vars."""

    _var_value: tuple[Var, ...] = dataclasses.field(default_factory=tuple)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        list_of_strs: list[str | Var] = []
        last_string = ""
        for var in self._var_value:
            if isinstance(var, LiteralStringVar):
                last_string += var._var_value
            else:
                if last_string:
                    list_of_strs.append(last_string)
                    last_string = ""
                list_of_strs.append(var)

        if last_string:
            list_of_strs.append(last_string)

        list_of_strs_filtered = [
            str(LiteralVar.create(s)) for s in list_of_strs if isinstance(s, Var) or s
        ]

        if len(list_of_strs_filtered) == 1:
            return list_of_strs_filtered[0]

        return "(" + "+".join(list_of_strs_filtered) + ")"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the VarData asVarDatae Var.

        Returns:
            The VarData associated with the Var.
        """
        return VarData.merge(
            *[
                var._get_all_var_data()
                for var in self._var_value
                if isinstance(var, Var)
            ],
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        *value: Var | str,
        _var_data: VarData | None = None,
    ) -> ConcatVarOperation:
        """Create a var from a string value.

        Args:
            *value: The values to concatenate.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _js_expr="",
            _var_type=str,
            _var_data=_var_data,
            _var_value=tuple(map(LiteralVar.create, value)),
        )


@var_operation
def string_split_operation(string: StringVar[Any], sep: StringVar | str = ""):
    """Split a string.

    Args:
        string: The string to split.
        sep: The separator.

    Returns:
        The split string.
    """
    return var_operation_return(
        js_expression=f"{string}.split({sep})", var_type=list[str]
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ArraySliceOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable string vars that are the result of a string slice operation."""

    _array: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )
    _start: NumberVar | int = dataclasses.field(default_factory=lambda: 0)
    _stop: NumberVar | int = dataclasses.field(default_factory=lambda: 0)
    _step: NumberVar | int = dataclasses.field(default_factory=lambda: 1)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.

        Raises:
            ValueError: If the slice step is zero.
        """
        start, end, step = self._start, self._stop, self._step

        normalized_start = (
            LiteralVar.create(start) if start is not None else Var(_js_expr="undefined")
        )
        normalized_end = (
            LiteralVar.create(end) if end is not None else Var(_js_expr="undefined")
        )
        if step is None:
            return f"{self._array!s}.slice({normalized_start!s}, {normalized_end!s})"
        if not isinstance(step, Var):
            if step < 0:
                actual_start = end + 1 if end is not None else 0
                actual_end = start + 1 if start is not None else self._array.length()
                return str(self._array[actual_start:actual_end].reverse()[::-step])
            if step == 0:
                msg = "slice step cannot be zero"
                raise ValueError(msg)
            return f"{self._array!s}.slice({normalized_start!s}, {normalized_end!s}).filter((_, i) => i % {step!s} === 0)"

        actual_start_reverse = end + 1 if end is not None else 0
        actual_end_reverse = start + 1 if start is not None else self._array.length()

        return f"{self.step!s} > 0 ? {self._array!s}.slice({normalized_start!s}, {normalized_end!s}).filter((_, i) => i % {step!s} === 0) : {self._array!s}.slice({actual_start_reverse!s}, {actual_end_reverse!s}).reverse().filter((_, i) => i % {-step!s} === 0)"

    @classmethod
    def create(
        cls,
        array: ArrayVar,
        slice: slice,
        _var_data: VarData | None = None,
    ) -> ArraySliceOperation:
        """Create a var from a string value.

        Args:
            array: The array.
            slice: The slice.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _js_expr="",
            _var_type=array._var_type,
            _var_data=_var_data,
            _array=array,
            _start=slice.start,
            _stop=slice.stop,
            _step=slice.step,
        )


@var_operation
def array_pluck_operation(
    array: ArrayVar[ARRAY_VAR_TYPE],
    field: StringVar | str,
) -> CustomVarOperationReturn[ARRAY_VAR_TYPE]:
    """Pluck a field from an array of objects.

    Args:
        array: The array to pluck from.
        field: The field to pluck from the objects in the array.

    Returns:
        The reversed array.
    """
    return var_operation_return(
        js_expression=f"{array}.map(e=>e?.[{field}])",
        var_type=array._var_type,
    )


@var_operation
def array_reverse_operation(
    array: ArrayVar[ARRAY_VAR_TYPE],
) -> CustomVarOperationReturn[ARRAY_VAR_TYPE]:
    """Reverse an array.

    Args:
        array: The array to reverse.

    Returns:
        The reversed array.
    """
    return var_operation_return(
        js_expression=f"{array}.slice().reverse()",
        var_type=array._var_type,
    )


@var_operation
def array_lt_operation(lhs: ArrayVar | list | tuple, rhs: ArrayVar | list | tuple):
    """Check if an array is less than another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array less than operation.
    """
    return var_operation_return(js_expression=f"{lhs} < {rhs}", var_type=bool)


@var_operation
def array_gt_operation(lhs: ArrayVar | list | tuple, rhs: ArrayVar | list | tuple):
    """Check if an array is greater than another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array greater than operation.
    """
    return var_operation_return(js_expression=f"{lhs} > {rhs}", var_type=bool)


@var_operation
def array_le_operation(lhs: ArrayVar | list | tuple, rhs: ArrayVar | list | tuple):
    """Check if an array is less than or equal to another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array less than or equal operation.
    """
    return var_operation_return(js_expression=f"{lhs} <= {rhs}", var_type=bool)


@var_operation
def array_ge_operation(lhs: ArrayVar | list | tuple, rhs: ArrayVar | list | tuple):
    """Check if an array is greater than or equal to another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array greater than or equal operation.
    """
    return var_operation_return(js_expression=f"{lhs} >= {rhs}", var_type=bool)


@var_operation
def array_length_operation(array: ArrayVar):
    """Get the length of an array.

    Args:
        array: The array.

    Returns:
        The length of the array.
    """
    return var_operation_return(
        js_expression=f"{array}.length",
        var_type=int,
    )


def is_tuple_type(t: GenericType) -> bool:
    """Check if a type is a tuple type.

    Args:
        t: The type to check.

    Returns:
        Whether the type is a tuple type.
    """
    return get_origin(t) is tuple


def _determine_value_of_array_index(
    var_type: GenericType, index: int | float | decimal.Decimal | None = None
):
    """Determine the value of an array index.

    Args:
        var_type: The type of the array.
        index: The index of the array.

    Returns:
        The value of the array index.
    """
    origin_var_type = get_origin(var_type) or var_type
    if origin_var_type in types.UnionTypes:
        return unionize(
            *[
                _determine_value_of_array_index(t, index)
                for t in get_args(var_type)
                if t is not type(None)
            ]
        )
    if origin_var_type is range:
        return int
    if origin_var_type in [
        Sequence,
        Iterable,
        list,
        set,
        collections.abc.Sequence,
        collections.abc.Iterable,
    ]:
        args = get_args(var_type)
        return args[0] if args else Any
    if origin_var_type is tuple:
        args = get_args(var_type)
        if len(args) == 2 and args[1] is ...:
            return args[0]
        return (
            args[int(index) % len(args)]
            if args and index is not None
            else (unionize(*args) if args else Any)
        )
    return Any


@var_operation
def array_item_operation(array: ArrayVar, index: NumberVar | int):
    """Get an item from an array.

    Args:
        array: The array.
        index: The index of the item.

    Returns:
        The item from the array.
    """
    element_type = _determine_value_of_array_index(
        array._var_type,
        (
            index
            if isinstance(index, int)
            else (index._var_value if isinstance(index, LiteralNumberVar) else None)
        ),
    )

    return var_operation_return(
        js_expression=f"{array!s}.at({index!s})",
        var_type=element_type,
    )


@var_operation
def array_range_operation(
    start: NumberVar | int, stop: NumberVar | int, step: NumberVar | int
):
    """Create a range of numbers.

    Args:
        start: The start of the range.
        stop: The end of the range.
        step: The step of the range.

    Returns:
        The range of numbers.
    """
    return var_operation_return(
        js_expression=f"Array.from({{ length: Math.ceil(({stop!s} - {start!s}) / {step!s}) }}, (_, i) => {start!s} + i * {step!s})",
        var_type=list[int],
    )


@var_operation
def array_contains_field_operation(
    haystack: ArrayVar, needle: Any | Var, field: StringVar | str
):
    """Check if an array contains an element.

    Args:
        haystack: The array to check.
        needle: The element to check for.
        field: The field to check.

    Returns:
        The array contains operation.
    """
    return var_operation_return(
        js_expression=f"{haystack}.some(obj => obj[{field}] === {needle})",
        var_type=bool,
    )


@var_operation
def array_contains_operation(
    haystack: ArrayVar, needle: Any | Var
) -> CustomVarOperationReturn[bool]:
    """Check if an array contains an element.

    Args:
        haystack: The array to check.
        needle: The element to check for.

    Returns:
        The array contains operation.
    """
    return var_operation_return(
        js_expression=f"{haystack}.includes({needle})",
        var_type=bool,
    )


@var_operation
def repeat_array_operation(
    array: ArrayVar[ARRAY_VAR_TYPE], count: NumberVar | int
) -> CustomVarOperationReturn[ARRAY_VAR_TYPE]:
    """Repeat an array a number of times.

    Args:
        array: The array to repeat.
        count: The number of times to repeat the array.

    Returns:
        The repeated array.
    """
    return var_operation_return(
        js_expression=f"Array.from({{ length: {count} }}).flatMap(() => {array})",
        var_type=array._var_type,
    )


@var_operation
def map_array_operation(
    array: ArrayVar[ARRAY_VAR_TYPE],
    function: FunctionVar,
) -> CustomVarOperationReturn[list[Any]]:
    """Map a function over an array.

    Args:
        array: The array.
        function: The function to map.

    Returns:
        The mapped array.
    """
    return var_operation_return(
        js_expression=f"{array}.map({function})", var_type=list[Any]
    )


@var_operation
def array_concat_operation(
    lhs: ArrayVar[ARRAY_VAR_TYPE], rhs: ArrayVar[ARRAY_VAR_TYPE]
) -> CustomVarOperationReturn[ARRAY_VAR_TYPE]:
    """Concatenate two arrays.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The concatenated array.
    """
    return var_operation_return(
        js_expression=f"[...{lhs}, ...{rhs}]",
        var_type=lhs._var_type | rhs._var_type,
    )


class ColorVar(StringVar[Color], python_types=Color):
    """Base class for immutable color vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralColorVar(CachedVarOperation, LiteralVar, ColorVar):
    """Base class for immutable literal color vars."""

    _var_value: Color = dataclasses.field(default_factory=lambda: Color(color="black"))

    @classmethod
    def create(
        cls,
        value: Color,
        _var_type: type[Color] | None = None,
        _var_data: VarData | None = None,
    ) -> ColorVar:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _js_expr="",
            _var_type=_var_type or Color,
            _var_data=_var_data,
            _var_value=value,
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash(
            (
                self.__class__.__name__,
                self._var_value.color,
                self._var_value.alpha,
                self._var_value.shade,
            )
        )

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        alpha = self._var_value.alpha
        alpha = (
            ternary_operation(
                alpha,
                LiteralStringVar.create("a"),
                LiteralStringVar.create(""),
            )
            if isinstance(alpha, Var)
            else LiteralStringVar.create("a" if alpha else "")
        )

        shade = self._var_value.shade
        shade = (
            shade.to_string(use_json=False)
            if isinstance(shade, Var)
            else LiteralStringVar.create(str(shade))
        )
        return str(
            ConcatVarOperation.create(
                LiteralStringVar.create("var(--"),
                self._var_value.color,
                LiteralStringVar.create("-"),
                alpha,
                shade,
                LiteralStringVar.create(")"),
            )
        )

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data.

        Returns:
            The var data.
        """
        return VarData.merge(
            *[
                LiteralVar.create(var)._get_all_var_data()
                for var in (
                    self._var_value.color,
                    self._var_value.alpha,
                    self._var_value.shade,
                )
            ],
            self._var_data,
        )

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.

        Raises:
            TypeError: If the color is not a valid color.
        """
        color, alpha, shade = map(
            get_python_literal,
            (self._var_value.color, self._var_value.alpha, self._var_value.shade),
        )
        if color is None or alpha is None or shade is None:
            msg = "Cannot serialize color that contains non-literal vars."
            raise TypeError(msg)
        if (
            not isinstance(color, str)
            or not isinstance(alpha, bool)
            or not isinstance(shade, int)
        ):
            msg = "Color is not a valid color."
            raise TypeError(msg)
        return f"var(--{color}-{'a' if alpha else ''}{shade})"


class RangeVar(ArrayVar[Sequence[int]], python_types=range):
    """Base class for immutable range vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralRangeVar(CachedVarOperation, LiteralVar, RangeVar):
    """Base class for immutable literal range vars."""

    _var_value: range = dataclasses.field(default_factory=lambda: range(0))

    @classmethod
    def create(
        cls,
        value: range,
        _var_type: type[range] | None = None,
        _var_data: VarData | None = None,
    ) -> RangeVar:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _js_expr="",
            _var_type=_var_type or range,
            _var_data=_var_data,
            _var_value=value,
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash(
            (
                self.__class__.__name__,
                self._var_value.start,
                self._var_value.stop,
                self._var_value.step,
            )
        )

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Array.from({{ length: Math.ceil(({self._var_value.stop!s} - {self._var_value.start!s}) / {self._var_value.step!s}) }}, (_, i) => {self._var_value.start!s} + i * {self._var_value.step!s})"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data.

        Returns:
            The var data.
        """
        return self._var_data

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return json.dumps(
            list(self._var_value),
        )
