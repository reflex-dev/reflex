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
    TypeVar,
    Union,
    overload,
)

from typing_extensions import get_origin

from reflex import constants
from reflex.constants.base import REFLEX_VAR_OPENING_TAG
from reflex.experimental.vars.base import (
    ImmutableVar,
    LiteralVar,
    figure_out_type,
    unionize,
)
from reflex.experimental.vars.number import (
    BooleanVar,
    LiteralNumberVar,
    NotEqualOperation,
    NumberVar,
)
from reflex.utils.types import GenericType
from reflex.vars import ImmutableVarData, Var, VarData, _global_vars

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
        return ConcatVarOperation(self, other)

    def __radd__(self, other: StringVar | str) -> ConcatVarOperation:
        """Concatenate two strings.

        Args:
            other: The other string.

        Returns:
            The string concatenation operation.
        """
        return ConcatVarOperation(other, self)

    def __mul__(self, other: int) -> ConcatVarOperation:
        """Concatenate two strings.

        Args:
            other: The other string.

        Returns:
            The string concatenation operation.
        """
        return ConcatVarOperation(*[self for _ in range(other)])

    def __rmul__(self, other: int) -> ConcatVarOperation:
        """Concatenate two strings.

        Args:
            other: The other string.

        Returns:
            The string concatenation operation.
        """
        return ConcatVarOperation(*[self for _ in range(other)])

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
        return StringItemOperation(self, i)

    def length(self) -> NumberVar:
        """Get the length of the string.

        Returns:
            The string length operation.
        """
        return self.split().length()

    def lower(self) -> StringLowerOperation:
        """Convert the string to lowercase.

        Returns:
            The string lower operation.
        """
        return StringLowerOperation(self)

    def upper(self) -> StringUpperOperation:
        """Convert the string to uppercase.

        Returns:
            The string upper operation.
        """
        return StringUpperOperation(self)

    def strip(self) -> StringStripOperation:
        """Strip the string.

        Returns:
            The string strip operation.
        """
        return StringStripOperation(self)

    def bool(self) -> NotEqualOperation:
        """Boolean conversion.

        Returns:
            The boolean value of the string.
        """
        return NotEqualOperation(self.length(), 0)

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
        return StringContainsOperation(self, other)

    def split(self, separator: StringVar | str = "") -> StringSplitOperation:
        """Split the string.

        Args:
            separator: The separator.

        Returns:
            The string split operation.
        """
        return StringSplitOperation(self, separator)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringToStringOperation(StringVar):
    """Base class for immutable string vars that are the result of a string to string operation."""

    a: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    def __init__(self, a: StringVar | str, _var_data: VarData | None = None):
        """Initialize the string to string operation var.

        Args:
            a: The string.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(StringToStringOperation, self).__init__(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self, "a", a if isinstance(a, Var) else LiteralStringVar.create(a)
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(
            "StringToStringOperation must implement _cached_var_name"
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
        getattr(super(StringToStringOperation, self), name)

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


class StringLowerOperation(StringToStringOperation):
    """Base class for immutable string vars that are the result of a string lower operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.toLowerCase()"


class StringUpperOperation(StringToStringOperation):
    """Base class for immutable string vars that are the result of a string upper operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.toUpperCase()"


class StringStripOperation(StringToStringOperation):
    """Base class for immutable string vars that are the result of a string strip operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.trim()"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringContainsOperation(BooleanVar):
    """Base class for immutable boolean vars that are the result of a string contains operation."""

    a: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    b: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    def __init__(
        self, a: StringVar | str, b: StringVar | str, _var_data: VarData | None = None
    ):
        """Initialize the string contains operation var.

        Args:
            a: The first string.
            b: The second string.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(StringContainsOperation, self).__init__(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self, "a", a if isinstance(a, Var) else LiteralStringVar.create(a)
        )
        object.__setattr__(
            self, "b", b if isinstance(b, Var) else LiteralStringVar.create(b)
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.includes({str(self.b)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(StringContainsOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(), self.b._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringItemOperation(StringVar):
    """Base class for immutable string vars that are the result of a string item operation."""

    a: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    i: NumberVar = dataclasses.field(default_factory=lambda: LiteralNumberVar(0))

    def __init__(
        self, a: StringVar | str, i: int | NumberVar, _var_data: VarData | None = None
    ):
        """Initialize the string item operation var.

        Args:
            a: The string.
            i: The index.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(StringItemOperation, self).__init__(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self, "a", a if isinstance(a, Var) else LiteralStringVar.create(a)
        )
        object.__setattr__(self, "i", i if isinstance(i, Var) else LiteralNumberVar(i))
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.at({str(self.i)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(StringItemOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(), self.i._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class ArrayJoinOperation(StringVar):
    """Base class for immutable string vars that are the result of an array join operation."""

    a: ArrayVar = dataclasses.field(default_factory=lambda: LiteralArrayVar([]))
    b: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    def __init__(
        self, a: ArrayVar, b: StringVar | str, _var_data: VarData | None = None
    ):
        """Initialize the array join operation var.

        Args:
            a: The array.
            b: The separator.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ArrayJoinOperation, self).__init__(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__setattr__(
            self, "b", b if isinstance(b, Var) else LiteralStringVar.create(b)
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.join({str(self.b)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ArrayJoinOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(), self.b._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


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


ARRAY_VAR_TYPE = TypeVar("ARRAY_VAR_TYPE", bound=Union[List, Tuple, Set])

OTHER_TUPLE = TypeVar("OTHER_TUPLE")

INNER_ARRAY_VAR = TypeVar("INNER_ARRAY_VAR")

KEY_TYPE = TypeVar("KEY_TYPE")
VALUE_TYPE = TypeVar("VALUE_TYPE")


class ArrayVar(ImmutableVar[ARRAY_VAR_TYPE]):
    """Base class for immutable array vars."""

    from reflex.experimental.vars.sequence import StringVar

    def join(self, sep: StringVar | str = "") -> ArrayJoinOperation:
        """Join the elements of the array.

        Args:
            sep: The separator between elements.

        Returns:
            The joined elements.
        """
        from reflex.experimental.vars.sequence import ArrayJoinOperation

        return ArrayJoinOperation(self, sep)

    def reverse(self) -> ArrayVar[ARRAY_VAR_TYPE]:
        """Reverse the array.

        Returns:
            The reversed array.
        """
        return ArrayReverseOperation(self)

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
            return ArraySliceOperation(self, i)
        return ArrayItemOperation(self, i).guess_type()

    def length(self) -> NumberVar:
        """Get the length of the array.

        Returns:
            The length of the array.
        """
        return ArrayLengthOperation(self)

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

        return RangeOperation(start, end, step or 1)

    def contains(self, other: Any) -> BooleanVar:
        """Check if the array contains an element.

        Args:
            other: The element to check for.

        Returns:
            The array contains operation.
        """
        return ArrayContainsOperation(self, other)


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
class LiteralArrayVar(LiteralVar, ArrayVar[ARRAY_VAR_TYPE]):
    """Base class for immutable literal array vars."""

    _var_value: Union[
        List[Union[Var, Any]], Set[Union[Var, Any]], Tuple[Union[Var, Any], ...]
    ] = dataclasses.field(default_factory=list)

    def __init__(
        self: LiteralArrayVar[ARRAY_VAR_TYPE],
        _var_value: ARRAY_VAR_TYPE,
        _var_type: type[ARRAY_VAR_TYPE] | None = None,
        _var_data: VarData | None = None,
    ):
        """Initialize the array var.

        Args:
            _var_value: The value of the var.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralArrayVar, self).__init__(
            _var_name="",
            _var_data=ImmutableVarData.merge(_var_data),
            _var_type=(figure_out_type(_var_value) if _var_type is None else _var_type),
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


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class StringSplitOperation(ArrayVar):
    """Base class for immutable array vars that are the result of a string split operation."""

    a: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    b: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    def __init__(
        self, a: StringVar | str, b: StringVar | str, _var_data: VarData | None = None
    ):
        """Initialize the string split operation var.

        Args:
            a: The string.
            b: The separator.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(StringSplitOperation, self).__init__(
            _var_name="",
            _var_type=List[str],
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self, "a", a if isinstance(a, Var) else LiteralStringVar.create(a)
        )
        object.__setattr__(
            self, "b", b if isinstance(b, Var) else LiteralStringVar.create(b)
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.split({str(self.b)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(StringSplitOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(), self.b._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayToArrayOperation(ArrayVar):
    """Base class for immutable array vars that are the result of an array to array operation."""

    a: ArrayVar = dataclasses.field(default_factory=lambda: LiteralArrayVar([]))

    def __init__(self, a: ArrayVar, _var_data: VarData | None = None):
        """Initialize the array to array operation var.

        Args:
            a: The string.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ArrayToArrayOperation, self).__init__(
            _var_name="",
            _var_type=a._var_type,
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
            "ArrayToArrayOperation must implement _cached_var_name"
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
        getattr(super(ArrayToArrayOperation, self), name)

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
class ArraySliceOperation(ArrayVar):
    """Base class for immutable string vars that are the result of a string slice operation."""

    a: ArrayVar = dataclasses.field(default_factory=lambda: LiteralArrayVar([]))
    _slice: slice = dataclasses.field(default_factory=lambda: slice(None, None, None))

    def __init__(self, a: ArrayVar, _slice: slice, _var_data: VarData | None = None):
        """Initialize the string slice operation var.

        Args:
            a: The string.
            _slice: The slice.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ArraySliceOperation, self).__init__(
            _var_name="",
            _var_type=a._var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "_slice", _slice)
        object.__delattr__(self, "_var_name")

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
            return (
                f"{str(self.a)}.slice({str(normalized_start)}, {str(normalized_end)})"
            )
        if not isinstance(step, Var):
            if step < 0:
                actual_start = end + 1 if end is not None else 0
                actual_end = start + 1 if start is not None else self.a.length()
                return str(
                    ArraySliceOperation(
                        ArrayReverseOperation(
                            ArraySliceOperation(self.a, slice(actual_start, actual_end))
                        ),
                        slice(None, None, -step),
                    )
                )
            if step == 0:
                raise ValueError("slice step cannot be zero")
            return f"{str(self.a)}.slice({str(normalized_start)}, {str(normalized_end)}).filter((_, i) => i % {str(step)} === 0)"

        actual_start_reverse = end + 1 if end is not None else 0
        actual_end_reverse = start + 1 if start is not None else self.a.length()

        return f"{str(self.step)} > 0 ? {str(self.a)}.slice({str(normalized_start)}, {str(normalized_end)}).filter((_, i) => i % {str(step)} === 0) : {str(self.a)}.slice({str(actual_start_reverse)}, {str(actual_end_reverse)}).reverse().filter((_, i) => i % {str(-step)} === 0)"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ArraySliceOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(),
            *[
                slice_value._get_all_var_data()
                for slice_value in (
                    self._slice.start,
                    self._slice.stop,
                    self._slice.step,
                )
                if slice_value is not None and isinstance(slice_value, Var)
            ],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class ArrayReverseOperation(ArrayToArrayOperation):
    """Base class for immutable string vars that are the result of a string reverse operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.reverse()"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayToNumberOperation(NumberVar):
    """Base class for immutable number vars that are the result of an array to number operation."""

    a: ArrayVar = dataclasses.field(
        default_factory=lambda: LiteralArrayVar([]),
    )

    def __init__(self, a: ArrayVar, _var_data: VarData | None = None):
        """Initialize the string to number operation var.

        Args:
            a: The array.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ArrayToNumberOperation, self).__init__(
            _var_name="",
            _var_type=int,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a if isinstance(a, Var) else LiteralArrayVar(a))
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError(
            "StringToNumberOperation must implement _cached_var_name"
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
        getattr(super(ArrayToNumberOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(self.a._get_all_var_data(), self._var_data)

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class ArrayLengthOperation(ArrayToNumberOperation):
    """Base class for immutable number vars that are the result of an array length operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.length"


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
class ArrayItemOperation(ImmutableVar):
    """Base class for immutable array vars that are the result of an array item operation."""

    a: ArrayVar = dataclasses.field(default_factory=lambda: LiteralArrayVar([]))
    i: NumberVar = dataclasses.field(default_factory=lambda: LiteralNumberVar(0))

    def __init__(
        self,
        a: ArrayVar,
        i: NumberVar | int,
        _var_data: VarData | None = None,
    ):
        """Initialize the array item operation var.

        Args:
            a: The array.
            i: The index.
            _var_data: Additional hooks and imports associated with the Var.
        """
        args = typing.get_args(a._var_type)
        if args and isinstance(i, int) and is_tuple_type(a._var_type):
            element_type = args[i % len(args)]
        else:
            element_type = unionize(*args)
        super(ArrayItemOperation, self).__init__(
            _var_name="",
            _var_type=element_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a if isinstance(a, Var) else LiteralArrayVar(a))
        object.__setattr__(
            self,
            "i",
            i if isinstance(i, Var) else LiteralNumberVar(i),
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.at({str(self.i)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ArrayItemOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(), self.i._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class RangeOperation(ArrayVar):
    """Base class for immutable array vars that are the result of a range operation."""

    start: NumberVar = dataclasses.field(default_factory=lambda: LiteralNumberVar(0))
    end: NumberVar = dataclasses.field(default_factory=lambda: LiteralNumberVar(0))
    step: NumberVar = dataclasses.field(default_factory=lambda: LiteralNumberVar(1))

    def __init__(
        self,
        start: NumberVar | int,
        end: NumberVar | int,
        step: NumberVar | int,
        _var_data: VarData | None = None,
    ):
        """Initialize the range operation var.

        Args:
            start: The start of the range.
            end: The end of the range.
            step: The step of the range.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(RangeOperation, self).__init__(
            _var_name="",
            _var_type=List[int],
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self,
            "start",
            start if isinstance(start, Var) else LiteralNumberVar(start),
        )
        object.__setattr__(
            self,
            "end",
            end if isinstance(end, Var) else LiteralNumberVar(end),
        )
        object.__setattr__(
            self,
            "step",
            step if isinstance(step, Var) else LiteralNumberVar(step),
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        start, end, step = self.start, self.end, self.step
        return f"Array.from({{ length: ({str(end)} - {str(start)}) / {str(step)} }}, (_, i) => {str(start)} + i * {str(step)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(RangeOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.start._get_all_var_data(),
            self.end._get_all_var_data(),
            self.step._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ArrayContainsOperation(BooleanVar):
    """Base class for immutable boolean vars that are the result of an array contains operation."""

    a: ArrayVar = dataclasses.field(default_factory=lambda: LiteralArrayVar([]))
    b: Var = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    def __init__(self, a: ArrayVar, b: Any | Var, _var_data: VarData | None = None):
        """Initialize the array contains operation var.

        Args:
            a: The array.
            b: The element to check for.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ArrayContainsOperation, self).__init__(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "b", b if isinstance(b, Var) else LiteralVar.create(b))
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.includes({str(self.b)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ArrayContainsOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(), self.b._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToStringOperation(StringVar):
    """Base class for immutable string vars that are the result of a to string operation."""

    original_var: Var = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    def __init__(self, original_var: Var, _var_data: VarData | None = None):
        """Initialize the to string operation var.

        Args:
            original_var: The original var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ToStringOperation, self).__init__(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self,
            "original_var",
            original_var,
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return str(self.original_var)

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ToStringOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.original_var._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToArrayOperation(ArrayVar):
    """Base class for immutable array vars that are the result of a to array operation."""

    original_var: Var = dataclasses.field(default_factory=lambda: LiteralArrayVar([]))

    def __init__(
        self,
        original_var: Var,
        _var_type: type[list] | type[set] | type[tuple] = list,
        _var_data: VarData | None = None,
    ):
        """Initialize the to array operation var.

        Args:
            original_var: The original var.
            _var_type: The type of the array.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(ToArrayOperation, self).__init__(
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self,
            "original_var",
            original_var,
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return str(self.original_var)

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(ToArrayOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.original_var._get_all_var_data(), self._var_data
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data
