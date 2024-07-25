"""Collection of string classes and utilities."""

from __future__ import annotations

import dataclasses
import functools
import json
import re
import sys
from functools import cached_property
from typing import Any, List, Set, Tuple, Union

from reflex import constants
from reflex.constants.base import REFLEX_VAR_OPENING_TAG
from reflex.experimental.vars.base import (
    ImmutableVar,
    LiteralVar,
)
from reflex.experimental.vars.number import BooleanVar, NotEqualOperation, NumberVar
from reflex.vars import ImmutableVarData, Var, VarData, _global_vars


class StringVar(ImmutableVar):
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

    def __getitem__(self, i: slice | int) -> StringSliceOperation | StringItemOperation:
        """Get a slice of the string.

        Args:
            i: The slice.

        Returns:
            The string slice operation.
        """
        if isinstance(i, slice):
            return StringSliceOperation(self, i)
        return StringItemOperation(self, i)

    def length(self) -> StringLengthOperation:
        """Get the length of the string.

        Returns:
            The string length operation.
        """
        return StringLengthOperation(self)

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

    def reversed(self) -> StringReverseOperation:
        """Reverse the string.

        Returns:
            The string reverse operation.
        """
        return StringReverseOperation(self)

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
class StringToNumberOperation(NumberVar):
    """Base class for immutable number vars that are the result of a string to number operation."""

    a: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    def __init__(self, a: StringVar | str, _var_data: VarData | None = None):
        """Initialize the string to number operation var.

        Args:
            a: The string.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(StringToNumberOperation, self).__init__(
            _var_name="",
            _var_type=float,
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
        getattr(super(StringToNumberOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(self.a._get_all_var_data(), self._var_data)

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class StringLengthOperation(StringToNumberOperation):
    """Base class for immutable number vars that are the result of a string length operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.length"


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


class StringReverseOperation(StringToStringOperation):
    """Base class for immutable string vars that are the result of a string reverse operation."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"{str(self.a)}.split('').reverse().join('')"


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
class StringSliceOperation(StringVar):
    """Base class for immutable string vars that are the result of a string slice operation."""

    a: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )
    _slice: slice = dataclasses.field(default_factory=lambda: slice(None, None, None))

    def __init__(
        self, a: StringVar | str, _slice: slice, _var_data: VarData | None = None
    ):
        """Initialize the string slice operation var.

        Args:
            a: The string.
            _slice: The slice.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(StringSliceOperation, self).__init__(
            _var_name="",
            _var_type=str,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self, "a", a if isinstance(a, Var) else LiteralStringVar.create(a)
        )
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

        if step is not None and step < 0:
            actual_start = end + 1 if end is not None else 0
            actual_end = start + 1 if start is not None else self.a.length()
            return str(
                StringSliceOperation(
                    StringReverseOperation(
                        StringSliceOperation(self.a, slice(actual_start, actual_end))
                    ),
                    slice(None, None, -step),
                )
            )

        start = (
            LiteralVar.create(start)
            if start is not None
            else ImmutableVar.create_safe("undefined")
        )
        end = (
            LiteralVar.create(end)
            if end is not None
            else ImmutableVar.create_safe("undefined")
        )

        if step is None:
            return f"{str(self.a)}.slice({str(start)}, {str(end)})"
        if step == 0:
            raise ValueError("slice step cannot be zero")
        return f"{str(self.a)}.slice({str(start)}, {str(end)}).split('').filter((_, i) => i % {str(step)} === 0).join('')"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute value.
        """
        if name == "_var_name":
            return self._cached_var_name
        getattr(super(StringSliceOperation, self), name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self.a._get_all_var_data(),
            self.start._get_all_var_data(),
            self.end._get_all_var_data(),
            self._var_data,
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
    i: int = dataclasses.field(default=0)

    def __init__(self, a: StringVar | str, i: int, _var_data: VarData | None = None):
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
        object.__setattr__(self, "i", i)
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
        return ImmutableVarData.merge(self.a._get_all_var_data(), self._var_data)

    def _get_all_var_data(self) -> ImmutableVarData | None:
        return self._cached_get_all_var_data


class ArrayJoinOperation(StringVar):
    """Base class for immutable string vars that are the result of an array join operation."""

    a: ArrayVar = dataclasses.field(default_factory=lambda: LiteralArrayVar([]))
    b: StringVar = dataclasses.field(
        default_factory=lambda: LiteralStringVar.create("")
    )

    def __init__(
        self, a: ArrayVar | list, b: StringVar | str, _var_data: VarData | None = None
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
        object.__setattr__(
            self, "a", a if isinstance(a, Var) else LiteralArrayVar.create(a)
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


class ArrayVar(ImmutableVar):
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


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralArrayVar(LiteralVar, ArrayVar):
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
            _var_type=list,
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
