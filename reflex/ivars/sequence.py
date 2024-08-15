"""Collection of string classes and utilities."""

from __future__ import annotations

import dataclasses
import functools
import inspect
import json
import re
import sys
import typing
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from typing_extensions import get_origin

from reflex import constants
from reflex.constants.base import REFLEX_VAR_OPENING_TAG
from reflex.utils.types import GenericType
from reflex.vars import ImmutableVarData, Var, VarData, _global_vars

from .base import (
    CachedVarOperation,
    ImmutableVar,
    LiteralVar,
    figure_out_type,
    unionize,
)
from .number import (
    BooleanVar,
    LiteralNumberVar,
    NotEqualOperation,
    NumberVar,
)

if TYPE_CHECKING:
    from .object import ObjectVar


class StringVar(ImmutableVar[str]):
    """Base class for immutable string vars."""

    def __add__(self, other: StringVar | str) -> ConcatVarOperation:
        """Concatenate two strings.

        Args:
            other: The other string.

        Returns:
            The string concatenation operation.
        """
        return ConcatVarOperation.create(self, other)

    def __radd__(self, other: StringVar | str) -> ConcatVarOperation:
        """Concatenate two strings.

        Args:
            other: The other string.

        Returns:
            The string concatenation operation.
        """
        return ConcatVarOperation.create(other, self)

    def __mul__(self, other: NumberVar | int) -> StringVar:
        """Multiply the sequence by a number or an integer.

        Args:
            other (NumberVar | int): The number or integer to multiply the sequence by.

        Returns:
            StringVar: The resulting sequence after multiplication.
        """
        return (self.split() * other).join()

    def __rmul__(self, other: NumberVar | int) -> StringVar:
        """Multiply the sequence by a number or an integer.

        Args:
            other (NumberVar | int): The number or integer to multiply the sequence by.

        Returns:
            StringVar: The resulting sequence after multiplication.
        """
        return (self.split() * other).join()

    @overload
    def __getitem__(self, i: slice) -> ArrayJoinOperation: ...

    @overload
    def __getitem__(self, i: int | NumberVar) -> StringItemOperation: ...

    def __getitem__(
        self, i: slice | int | NumberVar
    ) -> ArrayJoinOperation | StringItemOperation:
        """Get a slice of the string.

        Args:
            i: The slice.

        Returns:
            The string slice operation.
        """
        if isinstance(i, slice):
            return self.split()[i].join()
        return StringItemOperation.create(self, i)

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
        return StringLowerOperation.create(self)

    def upper(self) -> StringVar:
        """Convert the string to uppercase.

        Returns:
            The string upper operation.
        """
        return StringUpperOperation.create(self)

    def strip(self) -> StringVar:
        """Strip the string.

        Returns:
            The string strip operation.
        """
        return StringStripOperation.create(self)

    def bool(self) -> NotEqualOperation:
        """Boolean conversion.

        Returns:
            The boolean value of the string.
        """
        return NotEqualOperation.create(self.length(), 0)

    def reversed(self) -> ArrayJoinOperation:
        """Reverse the string.

        Returns:
            The string reverse operation.
        """
        return self.split().reverse().join()

    def contains(self, other: StringVar | str) -> StringContainsOperation:
        """Check if the string contains another string.

        Args:
            other: The other string.

        Returns:
            The string contains operation.
        """
        return StringContainsOperation.create(self, other)

    def split(self, separator: StringVar | str = "") -> StringSplitOperation:
        """Split the string.

        Args:
            separator: The separator.

        Returns:
            The string split operation.
        """
        return StringSplitOperation.create(self, separator)

    def startswith(self, prefix: StringVar | str) -> StringStartsWithOperation:
        """Check if the string starts with a prefix.

        Args:
            prefix: The prefix.

        Returns:
            The string starts with operation.
        """
        return StringStartsWithOperation.create(self, prefix)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringToStringOperation(CachedVarOperation, StringVar):
    """Base class for immutable string vars that are the result of a string to string operation."""

    _value: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(
            "StringToStringOperation must implement _cached_var_name"
        )

    @classmethod
    def create(
        cls,
        value: StringVar,
        _var_data: VarData | None = None,
    ) -> StringVar:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


class StringLowerOperation(StringToStringOperation):
    """Base class for immutable string vars that are the result of a string lower operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._value)}.toLowerCase()"


class StringUpperOperation(StringToStringOperation):
    """Base class for immutable string vars that are the result of a string upper operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._value)}.toUpperCase()"


class StringStripOperation(StringToStringOperation):
    """Base class for immutable string vars that are the result of a string strip operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._value)}.trim()"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringContainsOperation(CachedVarOperation, BooleanVar):
    """Base class for immutable boolean vars that are the result of a string contains operation."""

    _haystack: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    _needle: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._haystack)}.includes({str(self._needle)})"

    @classmethod
    def create(
        cls,
        haystack: StringVar | str,
        needle: StringVar | str,
        _var_data: VarData | None = None,
    ) -> StringContainsOperation:
        """Create a var from a string value.

        Args:
            haystack: The haystack.
            needle: The needle.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _haystack=(
                haystack
                if isinstance(haystack, Var)
                else LiteralStringVar.create(haystack)
            ),
            _needle=(
                needle if isinstance(needle, Var) else LiteralStringVar.create(needle)
            ),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringStartsWithOperation(CachedVarOperation, BooleanVar):
    """Base class for immutable boolean vars that are the result of a string starts with operation."""

    _full_string: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    _prefix: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._full_string)}.startsWith({str(self._prefix)})"

    @classmethod
    def create(
        cls,
        full_string: StringVar | str,
        prefix: StringVar | str,
        _var_data: VarData | None = None,
    ) -> StringStartsWithOperation:
        """Create a var from a string value.

        Args:
            full_string: The full string.
            prefix: The prefix.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _full_string=(
                full_string
                if isinstance(full_string, Var)
                else LiteralStringVar.create(full_string)
            ),
            _prefix=(
                prefix if isinstance(prefix, Var) else LiteralStringVar.create(prefix)
            ),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringItemOperation(CachedVarOperation, StringVar):
    """Base class for immutable string vars that are the result of a string item operation."""

    _string: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    _index: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._string)}.at({str(self._index)})"

    @classmethod
    def create(
        cls,
        string: StringVar | str,
        index: NumberVar | int,
        _var_data: VarData | None = None,
    ) -> StringItemOperation:
        """Create a var from a string value.

        Args:
            string: The string.
            index: The index.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
            _string=(
                string if isinstance(string, Var) else LiteralStringVar.create(string)
            ),
            _index=(
                index if isinstance(index, Var) else LiteralNumberVar.create(index)
            ),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayJoinOperation(CachedVarOperation, StringVar):
    """Base class for immutable string vars that are the result of an array join operation."""

    _array: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )
    _sep: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._array)}.join({str(self._sep)})"

    @classmethod
    def create(
        cls,
        array: ArrayVar,
        sep: StringVar | str = "",
        _var_data: VarData | None = None,
    ) -> ArrayJoinOperation:
        """Create a var from a string value.

        Args:
            array: The array.
            sep: The separator.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
            _array=array,
            _sep=sep if isinstance(sep, Var) else LiteralStringVar.create(sep),
        )


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
class LiteralStringVar(LiteralVar, StringVar):
    """Base class for immutable literal string vars."""

    _var_value: str = dataclasses.field(default="")

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
                        var_content = value[end : (end + string_length)]
                        if (
                            var_content[0] == "{"
                            and var_content[-1] == "}"
                            and strings_and_vals
                            and strings_and_vals[-1][-1] == "$"
                        ):
                            strings_and_vals[-1] = strings_and_vals[-1][:-1]
                            var_content = "(" + var_content[1:-1] + ")"
                        strings_and_vals.append(
                            ImmutableVar.create_safe(var_content, _var_data=var_data)
                        )
                        value = value[(end + string_length) :]

                offset += end - start

            strings_and_vals.append(value)

            filtered_strings_and_vals = [
                s for s in strings_and_vals if isinstance(s, Var) or s
            ]

            if len(filtered_strings_and_vals) == 1:
                return filtered_strings_and_vals[0].to(StringVar)  # type: ignore

            return ConcatVarOperation.create(
                *filtered_strings_and_vals,
                _var_data=_var_data,
            )

        return LiteralStringVar(
            _var_name=json.dumps(value),
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
            _var_value=value,
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

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


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ConcatVarOperation(CachedVarOperation, StringVar):
    """Representing a concatenation of literal string vars."""

    _var_value: Tuple[Var, ...] = dataclasses.field(default_factory=tuple)

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        list_of_strs: List[Union[str, Var]] = []
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

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all the VarData associated with the Var.

        Returns:
            The VarData associated with the Var.
        """
        return ImmutableVarData.merge(
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
            value: The values to concatenate.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
            _var_value=tuple(map(LiteralVar.create, value)),
        )


ARRAY_VAR_TYPE = TypeVar("ARRAY_VAR_TYPE", bound=Union[List, Tuple, Set])

OTHER_TUPLE = TypeVar("OTHER_TUPLE")

INNER_ARRAY_VAR = TypeVar("INNER_ARRAY_VAR")

KEY_TYPE = TypeVar("KEY_TYPE")
VALUE_TYPE = TypeVar("VALUE_TYPE")


class ArrayVar(ImmutableVar[ARRAY_VAR_TYPE]):
    """Base class for immutable array vars."""

    def join(self, sep: StringVar | str = "") -> ArrayJoinOperation:
        """Join the elements of the array.

        Args:
            sep: The separator between elements.

        Returns:
            The joined elements.
        """
        return ArrayJoinOperation.create(self, sep)

    def reverse(self) -> ArrayVar[ARRAY_VAR_TYPE]:
        """Reverse the array.

        Returns:
            The reversed array.
        """
        return ArrayReverseOperation.create(self)

    def __add__(self, other: ArrayVar[ARRAY_VAR_TYPE]) -> ArrayConcatOperation:
        """Concatenate two arrays.

        Parameters:
            other (ArrayVar[ARRAY_VAR_TYPE]): The other array to concatenate.

        Returns:
            ArrayConcatOperation: The concatenation of the two arrays.
        """
        return ArrayConcatOperation.create(self, other)

    @overload
    def __getitem__(self, i: slice) -> ArrayVar[ARRAY_VAR_TYPE]: ...

    @overload
    def __getitem__(
        self: (
            ArrayVar[Tuple[int, OTHER_TUPLE]]
            | ArrayVar[Tuple[float, OTHER_TUPLE]]
            | ArrayVar[Tuple[int | float, OTHER_TUPLE]]
        ),
        i: Literal[0, -2],
    ) -> NumberVar: ...

    @overload
    def __getitem__(
        self: (
            ArrayVar[Tuple[OTHER_TUPLE, int]]
            | ArrayVar[Tuple[OTHER_TUPLE, float]]
            | ArrayVar[Tuple[OTHER_TUPLE, int | float]]
        ),
        i: Literal[1, -1],
    ) -> NumberVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[Tuple[str, OTHER_TUPLE]], i: Literal[0, -2]
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[Tuple[OTHER_TUPLE, str]], i: Literal[1, -1]
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[Tuple[bool, OTHER_TUPLE]], i: Literal[0, -2]
    ) -> BooleanVar: ...

    @overload
    def __getitem__(
        self: ArrayVar[Tuple[OTHER_TUPLE, bool]], i: Literal[1, -1]
    ) -> BooleanVar: ...

    @overload
    def __getitem__(
        self: (
            ARRAY_VAR_OF_LIST_ELEMENT[int]
            | ARRAY_VAR_OF_LIST_ELEMENT[float]
            | ARRAY_VAR_OF_LIST_ELEMENT[int | float]
        ),
        i: int | NumberVar,
    ) -> NumberVar: ...

    @overload
    def __getitem__(
        self: ARRAY_VAR_OF_LIST_ELEMENT[str], i: int | NumberVar
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ARRAY_VAR_OF_LIST_ELEMENT[bool], i: int | NumberVar
    ) -> BooleanVar: ...

    @overload
    def __getitem__(
        self: ARRAY_VAR_OF_LIST_ELEMENT[List[INNER_ARRAY_VAR]],
        i: int | NumberVar,
    ) -> ArrayVar[List[INNER_ARRAY_VAR]]: ...

    @overload
    def __getitem__(
        self: ARRAY_VAR_OF_LIST_ELEMENT[Set[INNER_ARRAY_VAR]],
        i: int | NumberVar,
    ) -> ArrayVar[Set[INNER_ARRAY_VAR]]: ...

    @overload
    def __getitem__(
        self: ARRAY_VAR_OF_LIST_ELEMENT[Tuple[INNER_ARRAY_VAR, ...]],
        i: int | NumberVar,
    ) -> ArrayVar[Tuple[INNER_ARRAY_VAR, ...]]: ...

    @overload
    def __getitem__(
        self: ARRAY_VAR_OF_LIST_ELEMENT[Dict[KEY_TYPE, VALUE_TYPE]],
        i: int | NumberVar,
    ) -> ObjectVar[Dict[KEY_TYPE, VALUE_TYPE]]: ...

    @overload
    def __getitem__(self, i: int | NumberVar) -> ImmutableVar: ...

    def __getitem__(
        self, i: slice | int | NumberVar
    ) -> ArrayVar[ARRAY_VAR_TYPE] | ImmutableVar:
        """Get a slice of the array.

        Args:
            i: The slice.

        Returns:
            The array slice operation.
        """
        if isinstance(i, slice):
            return ArraySliceOperation.create(self, i)
        return ArrayItemOperation.create(self, i).guess_type()

    def length(self) -> NumberVar:
        """Get the length of the array.

        Returns:
            The length of the array.
        """
        return ArrayLengthOperation.create(self)

    @overload
    @classmethod
    def range(cls, stop: int | NumberVar, /) -> ArrayVar[List[int]]: ...

    @overload
    @classmethod
    def range(
        cls,
        start: int | NumberVar,
        end: int | NumberVar,
        step: int | NumberVar = 1,
        /,
    ) -> ArrayVar[List[int]]: ...

    @classmethod
    def range(
        cls,
        first_endpoint: int | NumberVar,
        second_endpoint: int | NumberVar | None = None,
        step: int | NumberVar | None = None,
    ) -> ArrayVar[List[int]]:
        """Create a range of numbers.

        Args:
            first_endpoint: The end of the range if second_endpoint is not provided, otherwise the start of the range.
            second_endpoint: The end of the range.
            step: The step of the range.

        Returns:
            The range of numbers.
        """
        if second_endpoint is None:
            start = 0
            end = first_endpoint
        else:
            start = first_endpoint
            end = second_endpoint

        return RangeOperation.create(start, end, step or 1)

    def contains(self, other: Any) -> BooleanVar:
        """Check if the array contains an element.

        Args:
            other: The element to check for.

        Returns:
            The array contains operation.
        """
        return ArrayContainsOperation.create(self, other)

    def __mul__(self, other: NumberVar | int) -> ArrayVar[ARRAY_VAR_TYPE]:
        """Multiply the sequence by a number or integer.

        Parameters:
            other (NumberVar | int): The number or integer to multiply the sequence by.

        Returns:
            ArrayVar[ARRAY_VAR_TYPE]: The result of multiplying the sequence by the given number or integer.
        """
        return ArrayRepeatOperation.create(self, other)

    __rmul__ = __mul__  # type: ignore


LIST_ELEMENT = TypeVar("LIST_ELEMENT")

ARRAY_VAR_OF_LIST_ELEMENT = Union[
    ArrayVar[List[LIST_ELEMENT]],
    ArrayVar[Set[LIST_ELEMENT]],
    ArrayVar[Tuple[LIST_ELEMENT, ...]],
]


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralArrayVar(CachedVarOperation, LiteralVar, ArrayVar[ARRAY_VAR_TYPE]):
    """Base class for immutable literal array vars."""

    _var_value: Union[
        List[Union[Var, Any]], Set[Union[Var, Any]], Tuple[Union[Var, Any], ...]
    ] = dataclasses.field(default_factory=list)

    @functools.cached_property
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

    @functools.cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all the VarData associated with the Var.

        Returns:
            The VarData associated with the Var.
        """
        return ImmutableVarData.merge(
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
        return hash((self.__class__.__name__, self._var_name))

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return (
            "["
            + ", ".join(
                [LiteralVar.create(element).json() for element in self._var_value]
            )
            + "]"
        )

    @classmethod
    def create(
        cls,
        value: ARRAY_VAR_TYPE,
        _var_type: Type[ARRAY_VAR_TYPE] | None = None,
        _var_data: VarData | None = None,
    ) -> LiteralArrayVar[ARRAY_VAR_TYPE]:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=figure_out_type(value) if _var_type is None else _var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _var_value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringSplitOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable array vars that are the result of a string split operation."""

    _string: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    _sep: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._string)}.split({str(self._sep)})"

    @classmethod
    def create(
        cls,
        string: StringVar | str,
        sep: StringVar | str,
        _var_data: VarData | None = None,
    ) -> StringSplitOperation:
        """Create a var from a string value.

        Args:
            string: The string.
            sep: The separator.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=List[str],
            _var_data=ImmutableVarData.merge(_var_data),
            _string=(
                string if isinstance(string, Var) else LiteralStringVar.create(string)
            ),
            _sep=(sep if isinstance(sep, Var) else LiteralStringVar.create(sep)),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayToArrayOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable array vars that are the result of an array to array operation."""

    _value: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(
            "ArrayToArrayOperation must implement _cached_var_name"
        )

    @classmethod
    def create(
        cls,
        value: ArrayVar,
        _var_data: VarData | None = None,
    ) -> ArrayToArrayOperation:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=value._var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArraySliceOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable string vars that are the result of a string slice operation."""

    _array: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )
    _slice: slice = dataclasses.field(default_factory=lambda: slice(None, None, None))

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.

        Raises:
            ValueError: If the slice step is zero.
        """
        start, end, step = self._slice.start, self._slice.stop, self._slice.step

        normalized_start = (
            LiteralVar.create(start)
            if start is not None
            else ImmutableVar.create_safe("undefined")
        )
        normalized_end = (
            LiteralVar.create(end)
            if end is not None
            else ImmutableVar.create_safe("undefined")
        )
        if step is None:
            return f"{str(self._array)}.slice({str(normalized_start)}, {str(normalized_end)})"
        if not isinstance(step, Var):
            if step < 0:
                actual_start = end + 1 if end is not None else 0
                actual_end = start + 1 if start is not None else self._array.length()
                return str(
                    ArraySliceOperation.create(
                        ArrayReverseOperation.create(
                            ArraySliceOperation.create(
                                self._array, slice(actual_start, actual_end)
                            )
                        ),
                        slice(None, None, -step),
                    )
                )
            if step == 0:
                raise ValueError("slice step cannot be zero")
            return f"{str(self._array)}.slice({str(normalized_start)}, {str(normalized_end)}).filter((_, i) => i % {str(step)} === 0)"

        actual_start_reverse = end + 1 if end is not None else 0
        actual_end_reverse = start + 1 if start is not None else self._array.length()

        return f"{str(self.step)} > 0 ? {str(self._array)}.slice({str(normalized_start)}, {str(normalized_end)}).filter((_, i) => i % {str(step)} === 0) : {str(self._array)}.slice({str(actual_start_reverse)}, {str(actual_end_reverse)}).reverse().filter((_, i) => i % {str(-step)} === 0)"

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
            _var_name="",
            _var_type=array._var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _array=array,
            _slice=slice,
        )


class ArrayReverseOperation(ArrayToArrayOperation):
    """Base class for immutable string vars that are the result of a string reverse operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._value)}.slice().reverse()"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayToNumberOperation(CachedVarOperation, NumberVar):
    """Base class for immutable number vars that are the result of an array to number operation."""

    _array: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([]),
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(
            "StringToNumberOperation must implement _cached_var_name"
        )

    @classmethod
    def create(
        cls,
        array: ArrayVar,
        _var_data: VarData | None = None,
    ) -> ArrayToNumberOperation:
        """Create a var from a string value.

        Args:
            array: The array.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=int,
            _var_data=ImmutableVarData.merge(_var_data),
            _array=array,
        )


class ArrayLengthOperation(ArrayToNumberOperation):
    """Base class for immutable number vars that are the result of an array length operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._array)}.length"


def is_tuple_type(t: GenericType) -> bool:
    """Check if a type is a tuple type.

    Args:
        t: The type to check.

    Returns:
        Whether the type is a tuple type.
    """
    if inspect.isclass(t):
        return issubclass(t, tuple)
    return get_origin(t) is tuple


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayItemOperation(CachedVarOperation, ImmutableVar):
    """Base class for immutable array vars that are the result of an array item operation."""

    _array: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )
    _index: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._array)}.at({str(self._index)})"

    @classmethod
    def create(
        cls,
        array: ArrayVar,
        index: NumberVar | int,
        _var_type: GenericType | None = None,
        _var_data: VarData | None = None,
    ) -> ArrayItemOperation:
        """Create a var from a string value.

        Args:
            array: The array.
            index: The index.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        args = typing.get_args(array._var_type)
        if args and isinstance(index, int) and is_tuple_type(array._var_type):
            element_type = args[index % len(args)]
        else:
            element_type = unionize(*args)

        return cls(
            _var_name="",
            _var_type=element_type if _var_type is None else _var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _array=array,
            _index=index if isinstance(index, Var) else LiteralNumberVar.create(index),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class RangeOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable array vars that are the result of a range operation."""

    _start: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )
    _stop: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )
    _step: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(1)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        start, end, step = self._start, self._stop, self._step
        return f"Array.from({{ length: ({str(end)} - {str(start)}) / {str(step)} }}, (_, i) => {str(start)} + i * {str(step)})"

    @classmethod
    def create(
        cls,
        start: NumberVar | int,
        stop: NumberVar | int,
        step: NumberVar | int,
        _var_data: VarData | None = None,
    ) -> RangeOperation:
        """Create a var from a string value.

        Args:
            start: The start of the range.
            stop: The end of the range.
            step: The step of the range.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=List[int],
            _var_data=ImmutableVarData.merge(_var_data),
            _start=start if isinstance(start, Var) else LiteralNumberVar.create(start),
            _stop=stop if isinstance(stop, Var) else LiteralNumberVar.create(stop),
            _step=step if isinstance(step, Var) else LiteralNumberVar.create(step),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayContainsOperation(CachedVarOperation, BooleanVar):
    """Base class for immutable boolean vars that are the result of an array contains operation."""

    _haystack: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )
    _needle: Var = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self._haystack)}.includes({str(self._needle)})"

    @classmethod
    def create(
        cls,
        haystack: ArrayVar,
        needle: Any | Var,
        _var_data: VarData | None = None,
    ) -> ArrayContainsOperation:
        """Create a var from a string value.

        Args:
            haystack: The array.
            needle: The element to check for.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _haystack=haystack,
            _needle=needle if isinstance(needle, Var) else LiteralVar.create(needle),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToStringOperation(CachedVarOperation, StringVar):
    """Base class for immutable string vars that are the result of a to string operation."""

    _original_var: Var = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return str(self._original_var)

    @classmethod
    def create(
        cls,
        original_var: Var,
        _var_data: VarData | None = None,
    ) -> ToStringOperation:
        """Create a var from a string value.

        Args:
            original_var: The original var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
            _original_var=original_var,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToArrayOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable array vars that are the result of a to array operation."""

    _original_var: Var = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return str(self._original_var)

    @classmethod
    def create(
        cls,
        original_var: Var,
        _var_type: type[list] | type[set] | type[tuple] | None = None,
        _var_data: VarData | None = None,
    ) -> ToArrayOperation:
        """Create a var from a string value.

        Args:
            original_var: The original var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=list if _var_type is None else _var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _original_var=original_var,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayRepeatOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable array vars that are the result of an array repeat operation."""

    _array: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )
    _count: NumberVar = dataclasses.field(
        default_factory=lambda: LiteralNumberVar.create(0)
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"Array.from({{ length: {str(self._count)} }}).flatMap(() => {str(self._array)})"

    @classmethod
    def create(
        cls,
        array: ArrayVar,
        count: NumberVar | int,
        _var_data: VarData | None = None,
    ) -> ArrayRepeatOperation:
        """Create a var from a string value.

        Args:
            array: The array.
            count: The number of times to repeat the array.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _var_name="",
            _var_type=array._var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _array=array,
            _count=count if isinstance(count, Var) else LiteralNumberVar.create(count),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayConcatOperation(CachedVarOperation, ArrayVar):
    """Base class for immutable array vars that are the result of an array concat operation."""

    _lhs: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )
    _rhs: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar.create([])
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"[...{str(self._lhs)}, ...{str(self._rhs)}]"

    @classmethod
    def create(
        cls,
        lhs: ArrayVar,
        rhs: ArrayVar,
        _var_data: VarData | None = None,
    ) -> ArrayConcatOperation:
        """Create a var from a string value.

        Args:
            lhs: The left-hand side array.
            rhs: The right-hand side array.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        # TODO: Figure out how to merge the types of a and b
        return cls(
            _var_name="",
            _var_type=Union[lhs._var_type, rhs._var_type],
            _var_data=ImmutableVarData.merge(_var_data),
            _lhs=lhs,
            _rhs=rhs,
        )
