"""Collection of string classes and utilities."""

from __future__ import annotations

import dataclasses
import functools
import inspect
import json
import re
import typing
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    List,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

from typing_extensions import TypeAliasType, TypeVar

from reflex import constants
from reflex.constants.base import REFLEX_VAR_OPENING_TAG
from reflex.constants.colors import Color
from reflex.utils.exceptions import VarTypeError
from reflex.utils.types import GenericType, get_origin
from reflex.vars.base import (
    CachedVarOperation,
    CustomVarOperationReturn,
    LiteralVar,
    ReflexCallable,
    Var,
    VarData,
    VarWithDefault,
    _global_vars,
    cached_property_no_lock,
    figure_out_type,
    get_python_literal,
    get_unique_variable_name,
    nary_type_computer,
    passthrough_unary_type_computer,
    unionize,
    unwrap_reflex_callalbe,
    var_operation,
    var_operation_return,
)

from .number import (
    _AT_SLICE_IMPORT,
    _AT_SLICE_OR_INDEX,
    _IS_TRUE_IMPORT,
    _RANGE_IMPORT,
    LiteralNumberVar,
    NumberVar,
    raise_unsupported_operand_types,
    ternary_operation,
)

if TYPE_CHECKING:
    from .function import FunctionVar

STRING_TYPE = TypeVar("STRING_TYPE", default=str)
ARRAY_VAR_TYPE = TypeVar("ARRAY_VAR_TYPE", bound=Union[Set, Tuple, Sequence])
OTHER_ARRAY_VAR_TYPE = TypeVar(
    "OTHER_ARRAY_VAR_TYPE", bound=Union[Set, Tuple, Sequence]
)

INNER_ARRAY_VAR = TypeVar("INNER_ARRAY_VAR", covariant=True)
ANOTHER_ARRAY_VAR = TypeVar("ANOTHER_ARRAY_VAR", covariant=True)

KEY_TYPE = TypeVar("KEY_TYPE")
VALUE_TYPE = TypeVar("VALUE_TYPE")


@var_operation
def string_lt_operation(lhs: Var[str], rhs: Var[str]):
    """Check if a string is less than another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string less than operation.
    """
    return var_operation_return(js_expression=f"({lhs} < {rhs})", var_type=bool)


@var_operation
def string_gt_operation(lhs: Var[str], rhs: Var[str]):
    """Check if a string is greater than another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string greater than operation.
    """
    return var_operation_return(js_expression=f"({lhs} > {rhs})", var_type=bool)


@var_operation
def string_le_operation(lhs: Var[str], rhs: Var[str]):
    """Check if a string is less than or equal to another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string less than or equal operation.
    """
    return var_operation_return(js_expression=f"({lhs} <= {rhs})", var_type=bool)


@var_operation
def string_ge_operation(lhs: Var[str], rhs: Var[str]):
    """Check if a string is greater than or equal to another string.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The string greater than or equal operation.
    """
    return var_operation_return(js_expression=f"({lhs} >= {rhs})", var_type=bool)


@var_operation
def string_lower_operation(string: Var[str]):
    """Convert a string to lowercase.

    Args:
        string: The string to convert.

    Returns:
        The lowercase string.
    """
    return var_operation_return(
        js_expression=f"String.prototype.toLowerCase.apply({string})",
        var_type=str,
        _raw_js_function="String.prototype.toLowerCase.apply",
    )


@var_operation
def string_upper_operation(string: Var[str]):
    """Convert a string to uppercase.

    Args:
        string: The string to convert.

    Returns:
        The uppercase string.
    """
    return var_operation_return(
        js_expression=f"String.prototype.toUpperCase.apply({string})",
        var_type=str,
        _raw_js_function="String.prototype.toUpperCase.apply",
    )


@var_operation
def string_strip_operation(string: Var[str]):
    """Strip a string.

    Args:
        string: The string to strip.

    Returns:
        The stripped string.
    """
    return var_operation_return(
        js_expression=f"String.prototype.trim.apply({string})",
        var_type=str,
        _raw_js_function="String.prototype.trim.apply",
    )


@var_operation
def string_contains_field_operation(
    haystack: Var[str],
    needle: Var[str],
):
    """Check if a string contains another string.

    Args:
        haystack: The haystack.
        needle: The needle.

    Returns:
        The string contains operation.
    """
    return var_operation_return(
        js_expression=f"{haystack}.includes({needle})",
        var_type=bool,
        var_data=VarData(
            imports=_IS_TRUE_IMPORT,
        ),
    )


@var_operation
def string_contains_operation(haystack: Var[str], needle: Var[str]):
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
def string_starts_with_operation(full_string: Var[str], prefix: Var[str]):
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
def string_ends_with_operation(full_string: Var[str], suffix: Var[str]):
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
def string_item_operation(string: Var[str], index: Var[int]):
    """Get an item from a string.

    Args:
        string: The string.
        index: The index of the item.

    Returns:
        The item from the string.
    """
    return var_operation_return(js_expression=f"{string}.at({index})", var_type=str)


@var_operation
def string_slice_operation(
    string: Var[str], slice: Var[slice]
) -> CustomVarOperationReturn[str]:
    """Get a slice from a string.

    Args:
        string: The string.
        slice: The slice.

    Returns:
        The sliced string.
    """
    return var_operation_return(
        js_expression=f'atSlice({string}.split(""), {slice}).join("")',
        type_computer=nary_type_computer(
            ReflexCallable[[List[str], slice], str],
            ReflexCallable[[slice], str],
            computer=lambda args: str,
        ),
        var_data=VarData(
            imports=_AT_SLICE_IMPORT,
        ),
    )


@var_operation
def string_index_or_slice_operation(
    string: Var[str], index_or_slice: Var[Union[int, slice]]
) -> CustomVarOperationReturn[Union[str, Sequence[str]]]:
    """Get an item or slice from a string.

    Args:
        string: The string.
        index_or_slice: The index or slice.

    Returns:
        The item or slice from the string.
    """
    return var_operation_return(
        js_expression=f"Array.prototype.join.apply(atSliceOrIndex({string}, {index_or_slice}), [''])",
        _raw_js_function="atSliceOrIndex",
        type_computer=nary_type_computer(
            ReflexCallable[[List[str], Union[int, slice]], str],
            ReflexCallable[[Union[int, slice]], str],
            computer=lambda args: str,
        ),
        var_data=VarData(
            imports=_AT_SLICE_OR_INDEX,
        ),
    )


@var_operation
def string_replace_operation(
    string: Var[str], search_value: Var[str], new_value: Var[str]
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
        js_expression=f"{string}.replace({search_value}, {new_value})",
        var_type=str,
    )


@var_operation
def array_pluck_operation(
    array: Var[Sequence[Any]],
    field: Var[str],
) -> CustomVarOperationReturn[Sequence[Any]]:
    """Pluck a field from an array of objects.

    Args:
        array: The array to pluck from.
        field: The field to pluck from the objects in the array.

    Returns:
        The reversed array.
    """
    return var_operation_return(
        js_expression=f"Array.prototype.map.apply({array}, [e=>e?.[{field}]])",
        var_type=List[Any],
    )


@var_operation
def array_join_operation(
    array: Var[Sequence[Any]], sep: VarWithDefault[str] = VarWithDefault("")
):
    """Join the elements of an array.

    Args:
        array: The array.
        sep: The separator.

    Returns:
        The joined elements.
    """
    return var_operation_return(
        js_expression=f"Array.prototype.join.apply({array},[{sep}])", var_type=str
    )


@var_operation
def array_reverse_operation(
    array: Var[Sequence[INNER_ARRAY_VAR]],
) -> CustomVarOperationReturn[Sequence[INNER_ARRAY_VAR]]:
    """Reverse an array.

    Args:
        array: The array to reverse.

    Returns:
        The reversed array.
    """
    return var_operation_return(
        js_expression=f"{array}.slice().reverse()",
        type_computer=passthrough_unary_type_computer(ReflexCallable[[List], List]),
    )


@var_operation
def array_lt_operation(lhs: Var[ARRAY_VAR_TYPE], rhs: Var[ARRAY_VAR_TYPE]):
    """Check if an array is less than another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array less than operation.
    """
    return var_operation_return(js_expression=f"{lhs} < {rhs}", var_type=bool)


@var_operation
def array_gt_operation(lhs: Var[ARRAY_VAR_TYPE], rhs: Var[ARRAY_VAR_TYPE]):
    """Check if an array is greater than another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array greater than operation.
    """
    return var_operation_return(js_expression=f"{lhs} > {rhs}", var_type=bool)


@var_operation
def array_le_operation(lhs: Var[ARRAY_VAR_TYPE], rhs: Var[ARRAY_VAR_TYPE]):
    """Check if an array is less than or equal to another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array less than or equal operation.
    """
    return var_operation_return(js_expression=f"{lhs} <= {rhs}", var_type=bool)


@var_operation
def array_ge_operation(lhs: Var[ARRAY_VAR_TYPE], rhs: Var[ARRAY_VAR_TYPE]):
    """Check if an array is greater than or equal to another array.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The array greater than or equal operation.
    """
    return var_operation_return(js_expression=f"{lhs} >= {rhs}", var_type=bool)


@var_operation
def array_length_operation(array: Var[ARRAY_VAR_TYPE]):
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


@var_operation
def string_split_operation(
    string: Var[str], sep: VarWithDefault[str] = VarWithDefault("")
):
    """Split a string.

    Args:
        string: The string to split.
        sep: The separator.

    Returns:
        The split string.
    """
    return var_operation_return(
        js_expression=f"isTrue({sep}) ? {string}.split({sep}) : [...{string}]",
        var_type=Sequence[str],
        var_data=VarData(imports=_IS_TRUE_IMPORT),
    )


def _element_type(array: Var, index: Var) -> Any:
    array_args = typing.get_args(array._var_type)

    if (
        array_args
        and isinstance(index, LiteralNumberVar)
        and is_tuple_type(array._var_type)
    ):
        index_value = int(index._var_value)
        return array_args[index_value % len(array_args)]

    return unionize(*(array_arg for array_arg in array_args if array_arg is not ...))


@var_operation
def array_item_or_slice_operation(
    array: Var[Sequence[INNER_ARRAY_VAR]],
    index_or_slice: Var[Union[int, slice]],
) -> CustomVarOperationReturn[Union[INNER_ARRAY_VAR, Sequence[INNER_ARRAY_VAR]]]:
    """Get an item or slice from an array.

    Args:
        array: The array.
        index_or_slice: The index or slice.

    Returns:
        The item or slice from the array.
    """
    return var_operation_return(
        js_expression=f"atSliceOrIndex({array}, {index_or_slice})",
        _raw_js_function="atSliceOrIndex",
        type_computer=nary_type_computer(
            ReflexCallable[[Sequence, Union[int, slice]], Any],
            ReflexCallable[[Union[int, slice]], Any],
            computer=lambda args: (
                args[0]._var_type
                if args[1]._var_type is slice
                else (_element_type(args[0], args[1]))
            ),
        ),
        var_data=VarData(
            imports=_AT_SLICE_OR_INDEX,
        ),
    )


@var_operation
def array_slice_operation(
    array: Var[Sequence[INNER_ARRAY_VAR]],
    slice: Var[slice],
) -> CustomVarOperationReturn[Sequence[INNER_ARRAY_VAR]]:
    """Get a slice from an array.

    Args:
        array: The array.
        slice: The slice.

    Returns:
        The item or slice from the array.
    """
    return var_operation_return(
        js_expression=f"atSlice({array}, {slice})",
        type_computer=nary_type_computer(
            ReflexCallable[[List, slice], Any],
            ReflexCallable[[slice], Any],
            computer=lambda args: args[0]._var_type,
        ),
        var_data=VarData(
            imports=_AT_SLICE_IMPORT,
        ),
    )


@var_operation
def array_item_operation(
    array: Var[Sequence[INNER_ARRAY_VAR]], index: Var[int]
) -> CustomVarOperationReturn[INNER_ARRAY_VAR]:
    """Get an item from an array.

    Args:
        array: The array.
        index: The index of the item.

    Returns:
        The item from the array.
    """

    def type_computer(*args):
        if len(args) == 0:
            return (
                ReflexCallable[[List[Any], int], Any],
                functools.partial(type_computer, *args),
            )

        array = args[0]
        array_args = typing.get_args(array._var_type)

        if len(args) == 1:
            return (
                ReflexCallable[[int], unionize(*array_args)],
                functools.partial(type_computer, *args),
            )

        index = args[1]

        if (
            array_args
            and isinstance(index, LiteralNumberVar)
            and is_tuple_type(array._var_type)
        ):
            index_value = int(index._var_value)
            element_type = array_args[index_value % len(array_args)]
        else:
            element_type = unionize(*array_args)

        return (ReflexCallable[[], element_type], None)

    return var_operation_return(
        js_expression=f"{array}.at({index})",
        type_computer=type_computer,
    )


@var_operation
def array_range_operation(
    e1: Var[int],
    e2: VarWithDefault[int | None] = VarWithDefault(None),
    step: VarWithDefault[int] = VarWithDefault(1),
) -> CustomVarOperationReturn[Sequence[int]]:
    """Create a range of numbers.

    Args:
        e1: The end of the range if e2 is not provided, otherwise the start of the range.
        e2: The end of the range.
        step: The step of the range.

    Returns:
        The range of numbers.
    """
    return var_operation_return(
        js_expression=f"[...range({e1}, {e2}, {step})]",
        var_type=List[int],
        var_data=VarData(
            imports=_RANGE_IMPORT,
        ),
    )


@var_operation
def array_contains_field_operation(
    haystack: Var[ARRAY_VAR_TYPE],
    needle: Var[Any],
    field: VarWithDefault[str] = VarWithDefault(""),
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
        js_expression=f"isTrue({field}) ? {haystack}.some(obj => obj[{field}] === {needle}) : {haystack}.some(obj => obj === {needle})",
        var_type=bool,
        var_data=VarData(
            imports=_IS_TRUE_IMPORT,
        ),
    )


@var_operation
def array_contains_operation(haystack: Var[ARRAY_VAR_TYPE], needle: Var):
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
    array: Var[Sequence[INNER_ARRAY_VAR]], count: Var[int]
) -> CustomVarOperationReturn[Sequence[INNER_ARRAY_VAR]]:
    """Repeat an array a number of times.

    Args:
        array: The array to repeat.
        count: The number of times to repeat the array.

    Returns:
        The repeated array.
    """

    def type_computer(*args: Var):
        if not args:
            return (
                ReflexCallable[[List[Any], int], List[Any]],
                type_computer,
            )
        if len(args) == 1:
            return (
                ReflexCallable[[int], args[0]._var_type],
                functools.partial(type_computer, *args),
            )
        return (ReflexCallable[[], args[0]._var_type], None)

    return var_operation_return(
        js_expression=f"Array.from({{ length: {count} }}).flatMap(() => {array})",
        type_computer=type_computer,
    )


@var_operation
def repeat_string_operation(
    string: Var[str], count: Var[int]
) -> CustomVarOperationReturn[str]:
    """Repeat a string a number of times.

    Args:
        string: The string to repeat.
        count: The number of times to repeat the string.

    Returns:
        The repeated string.
    """
    return var_operation_return(
        js_expression=f"{string}.repeat({count})",
        var_type=str,
    )


if TYPE_CHECKING:
    pass


@var_operation
def map_array_operation(
    array: Var[Sequence[INNER_ARRAY_VAR]],
    function: Var[
        ReflexCallable[[INNER_ARRAY_VAR, int], ANOTHER_ARRAY_VAR]
        | ReflexCallable[[INNER_ARRAY_VAR], ANOTHER_ARRAY_VAR]
        | ReflexCallable[[], ANOTHER_ARRAY_VAR]
    ],
) -> CustomVarOperationReturn[Sequence[ANOTHER_ARRAY_VAR]]:
    """Map a function over an array.

    Args:
        array: The array.
        function: The function to map.

    Returns:
        The mapped array.
    """

    def type_computer(*args: Var):
        if not args:
            return (
                ReflexCallable[[List[Any], ReflexCallable], List[Any]],
                type_computer,
            )
        if len(args) == 1:
            return (
                ReflexCallable[[ReflexCallable], List[Any]],
                functools.partial(type_computer, *args),
            )
        return (ReflexCallable[[], List[args[0]._var_type]], None)

    return var_operation_return(
        js_expression=f"Array.prototype.map.apply({array}, [{function}])",
        type_computer=nary_type_computer(
            ReflexCallable[[List[Any], ReflexCallable], List[Any]],
            ReflexCallable[[ReflexCallable], List[Any]],
            computer=lambda args: List[unwrap_reflex_callalbe(args[1]._var_type)[1]],
        ),
    )


@var_operation
def array_concat_operation(
    lhs: Var[Sequence[INNER_ARRAY_VAR]], rhs: Var[Sequence[ANOTHER_ARRAY_VAR]]
) -> CustomVarOperationReturn[Sequence[INNER_ARRAY_VAR | ANOTHER_ARRAY_VAR]]:
    """Concatenate two arrays.

    Args:
        lhs: The left-hand side array.
        rhs: The right-hand side array.

    Returns:
        The concatenated array.
    """
    return var_operation_return(
        js_expression=f"[...{lhs}, ...{rhs}]",
        type_computer=nary_type_computer(
            ReflexCallable[[List[Any], List[Any]], List[Any]],
            ReflexCallable[[List[Any]], List[Any]],
            computer=lambda args: unionize(args[0]._var_type, args[1]._var_type),
        ),
    )


@var_operation
def string_concat_operation(
    lhs: Var[str], rhs: Var[str]
) -> CustomVarOperationReturn[str]:
    """Concatenate two strings.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The concatenated string.
    """
    return var_operation_return(
        js_expression=f"{lhs} + {rhs}",
        var_type=str,
    )


@var_operation
def reverse_string_concat_operation(
    lhs: Var[str], rhs: Var[str]
) -> CustomVarOperationReturn[str]:
    """Concatenate two strings in reverse order.

    Args:
        lhs: The left-hand side string.
        rhs: The right-hand side string.

    Returns:
        The concatenated string.
    """
    return var_operation_return(
        js_expression=f"{rhs} + {lhs}",
        var_type=str,
    )


class SliceVar(Var[slice], python_types=slice):
    """Base class for immutable slice vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralSliceVar(CachedVarOperation, LiteralVar, SliceVar):
    """Base class for immutable literal slice vars."""

    _var_value: slice = dataclasses.field(default_factory=lambda: slice(None))

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"[{LiteralVar.create(self._var_value.start)!s}, {LiteralVar.create(self._var_value.stop)!s}, {LiteralVar.create(self._var_value.step)!s}]"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the VarData asVarDatae Var.

        Returns:
            The VarData associated with the Var.
        """
        return VarData.merge(
            *[
                var._get_all_var_data()
                for var in [
                    self._var_value.start,
                    self._var_value.stop,
                    self._var_value.step,
                ]
                if isinstance(var, Var)
            ],
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        value: slice,
        _var_type: Type[slice] | None = None,
        _var_data: VarData | None = None,
    ) -> SliceVar:
        """Create a var from a slice value.

        Args:
            value: The value to create the var from.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _js_expr="",
            _var_type=slice if _var_type is None else _var_type,
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

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return json.dumps(
            [self._var_value.start, self._var_value.stop, self._var_value.step]
        )


class ArrayVar(Var[ARRAY_VAR_TYPE], python_types=(Sequence, set)):
    """Base class for immutable array vars."""

    join = array_join_operation

    reverse = array_reverse_operation

    __add__ = array_concat_operation

    __getitem__ = array_item_or_slice_operation

    at = array_item_operation

    slice = array_slice_operation

    length = array_length_operation

    range: ClassVar[
        FunctionVar[
            ReflexCallable[
                [int, VarWithDefault[int | None], VarWithDefault[int]], Sequence[int]
            ]
        ]
    ] = array_range_operation

    contains = array_contains_field_operation

    pluck = array_pluck_operation

    __rmul__ = __mul__ = repeat_array_operation

    __lt__ = array_lt_operation

    __gt__ = array_gt_operation

    __le__ = array_le_operation

    __ge__ = array_ge_operation

    def foreach(
        self: ArrayVar[Sequence[INNER_ARRAY_VAR]],
        fn: Callable[[Var[INNER_ARRAY_VAR], NumberVar[int]], ANOTHER_ARRAY_VAR]
        | Callable[[Var[INNER_ARRAY_VAR]], ANOTHER_ARRAY_VAR]
        | Callable[[], ANOTHER_ARRAY_VAR],
    ) -> ArrayVar[Sequence[ANOTHER_ARRAY_VAR]]:
        """Apply a function to each element of the array.

        Args:
            fn: The function to apply.

        Returns:
            The array after applying the function.

        Raises:
            VarTypeError: If the function takes more than one argument.
            TypeError: If the function is a ComponentState.
        """
        from reflex.state import ComponentState

        from .function import ArgsFunctionOperation

        if not callable(fn):
            raise_unsupported_operand_types("foreach", (type(self), type(fn)))

        # get the number of arguments of the function
        required_num_args = len(
            [
                p
                for p in inspect.signature(fn).parameters.values()
                if p.default == p.empty
            ]
        )
        if required_num_args > 2:
            raise VarTypeError(
                "The function passed to foreach should take at most two arguments."
            )

        num_args = len(inspect.signature(fn).parameters)

        if (
            hasattr(fn, "__qualname__")
            and fn.__qualname__ == ComponentState.create.__qualname__
        ):
            raise TypeError(
                "Using a ComponentState as `render_fn` inside `rx.foreach` is not supported yet."
            )

        if num_args == 0:
            fn_result = fn()  # pyright: ignore [reportCallIssue]
            return_value = Var.create(fn_result)
            simple_function_var: FunctionVar[ReflexCallable[[], ANOTHER_ARRAY_VAR]] = (
                ArgsFunctionOperation.create(
                    (),
                    return_value,
                    _var_type=ReflexCallable[[], return_value._var_type],
                )
            )
            return map_array_operation(self, simple_function_var).guess_type()

        # generic number var
        number_var = Var("").to(NumberVar, int)

        first_arg_type = self.__getitem__(number_var)._var_type

        arg_name = get_unique_variable_name()

        # get first argument type
        first_arg = cast(
            Var[Any],
            Var(
                _js_expr=arg_name,
                _var_type=first_arg_type,
            ).guess_type(),
        )

        if required_num_args < 2:
            fn_result = fn(first_arg)  # pyright: ignore [reportCallIssue]

            return_value = Var.create(fn_result)

            function_var = cast(
                Var[ReflexCallable[[INNER_ARRAY_VAR], ANOTHER_ARRAY_VAR]],
                ArgsFunctionOperation.create(
                    (arg_name,),
                    return_value,
                    _var_type=ReflexCallable[[first_arg_type], return_value._var_type],
                ),
            )

            return map_array_operation.call(self, function_var).guess_type()

        second_arg = cast(
            NumberVar[int],
            Var(
                _js_expr=get_unique_variable_name(),
                _var_type=int,
            ).guess_type(),
        )

        fn_result = fn(first_arg, second_arg)  # pyright: ignore [reportCallIssue]

        return_value = Var.create(fn_result)

        function_var = cast(
            Var[ReflexCallable[[INNER_ARRAY_VAR, int], ANOTHER_ARRAY_VAR]],
            ArgsFunctionOperation.create(
                (arg_name, second_arg._js_expr),
                return_value,
                _var_type=ReflexCallable[[first_arg_type, int], return_value._var_type],
            ),
        )

        return map_array_operation.call(self, function_var).guess_type()


LIST_ELEMENT = TypeVar("LIST_ELEMENT", covariant=True)

ARRAY_VAR_OF_LIST_ELEMENT = TypeAliasType(
    "ARRAY_VAR_OF_LIST_ELEMENT",
    Union[
        ArrayVar[Sequence[LIST_ELEMENT]],
        ArrayVar[Set[LIST_ELEMENT]],
    ],
    type_params=(LIST_ELEMENT,),
)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralArrayVar(CachedVarOperation, LiteralVar, ArrayVar[ARRAY_VAR_TYPE]):
    """Base class for immutable literal array vars."""

    _var_value: Union[
        Sequence[Union[Var, Any]],
        Set[Union[Var, Any]],
    ] = dataclasses.field(default_factory=list)

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
                raise TypeError(
                    f"Array elements must be of type LiteralVar, not {type(element_var)}"
                )
            elements.append(element_var.json())

        return "[" + ", ".join(elements) + "]"

    @classmethod
    def create(
        cls,
        value: OTHER_ARRAY_VAR_TYPE,
        _var_type: Type[OTHER_ARRAY_VAR_TYPE] | None = None,
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


class StringVar(Var[STRING_TYPE], python_types=str):
    """Base class for immutable string vars."""

    __add__ = string_concat_operation

    __radd__ = reverse_string_concat_operation

    __getitem__ = string_index_or_slice_operation

    at = string_item_operation

    slice = string_slice_operation

    lower = string_lower_operation

    upper = string_upper_operation

    strip = string_strip_operation

    contains = string_contains_field_operation

    split = string_split_operation

    length = split.chain(array_length_operation)

    reversed = split.chain(array_reverse_operation).chain(array_join_operation)

    startswith = string_starts_with_operation

    __rmul__ = __mul__ = repeat_string_operation

    __lt__ = string_lt_operation

    __gt__ = string_gt_operation

    __le__ = string_le_operation

    __ge__ = string_ge_operation


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
                else:
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
    slots=True,
)
class ConcatVarOperation(CachedVarOperation, StringVar[str]):
    """Representing a concatenation of literal string vars."""

    _var_value: Tuple[Var, ...] = dataclasses.field(default_factory=tuple)

    @cached_property_no_lock
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
            value: The values to concatenate.
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
        _var_type: Type[Color] | None = None,
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
        alpha = cast(Union[Var[bool], bool], self._var_value.alpha)
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
            raise TypeError("Cannot serialize color that contains non-literal vars.")
        if (
            not isinstance(color, str)
            or not isinstance(alpha, bool)
            or not isinstance(shade, int)
        ):
            raise TypeError("Color is not a valid color.")
        return f"var(--{color}-{'a' if alpha else ''}{shade})"
