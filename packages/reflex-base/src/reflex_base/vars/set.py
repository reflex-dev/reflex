"""Immutable set vars.

A set travels to the frontend as a JSON array (see ``serialize_set``), the same
value that comes back through event arguments, so every operation here compiles
to JavaScript over that array. Operations that produce a set yield an array
without duplicates; membership-style operations build a JS ``Set`` only inside
the compiled expression.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, TypeVar, overload

from reflex_base.utils import console
from reflex_base.utils.types import GenericType, get_origin, unionize

from .base import (
    CachedVarOperation,
    CustomVarOperationReturn,
    LiteralVar,
    Var,
    VarData,
    cached_property_no_lock,
    figure_out_type,
    var_operation,
    var_operation_return,
)
from .number import BooleanVar, NumberVar, raise_unsupported_operand_types
from .sequence import (
    ArrayVar,
    _determine_value_of_array_index,
    _literal_elements_json,
    _literal_elements_var_data,
)

if TYPE_CHECKING:
    from typing_extensions import deprecated

SET_VAR_TYPE = TypeVar("SET_VAR_TYPE", bound=set | frozenset, covariant=True)
OTHER_SET_VAR_TYPE = TypeVar("OTHER_SET_VAR_TYPE", bound=set | frozenset)
SET_ELEMENT = TypeVar("SET_ELEMENT")

_OTHER_SET_TYPES = (set, frozenset, list, tuple)

_ARRAY_OPERATION_REASON = (
    "A set is not a sequence; call .to_array() first to use array operations."
)


def _element_type(var_type: GenericType) -> GenericType:
    """Get the element type of a set type.

    Args:
        var_type: The set type, e.g. ``set[str]``.

    Returns:
        The element type, or Any for an unparameterized set.
    """
    return _determine_value_of_array_index(var_type)


def _set_type_like(var_type: GenericType, element_type: GenericType) -> GenericType:
    """Build a set type with the given element type, keeping frozenset-ness.

    Args:
        var_type: The set type whose origin (set or frozenset) to keep.
        element_type: The element type of the resulting set.

    Returns:
        ``set[element_type]``, or ``frozenset[element_type]`` for a frozenset.
    """
    origin = get_origin(var_type) or var_type
    return (frozenset if origin is frozenset else set)[element_type]


def _deprecated_array_operation(name: str) -> Callable[..., Any]:
    """Make a method that runs an array operation on the set as an array.

    The method warns that the operation is deprecated on sets, then delegates
    to the same operation on ``to_array()``.

    Args:
        name: The name of the array operation.

    Returns:
        The method.
    """

    def operation(self: SetVar, *args: Any, **kwargs: Any) -> Any:
        console.deprecate(
            feature_name=f"SetVar.{name}",
            reason=_ARRAY_OPERATION_REASON,
            deprecation_version="0.10.0",
            removal_version="1.0",
        )
        return getattr(self.to_array(), name)(*args, **kwargs)

    operation.__name__ = name
    return operation


def _check_other(operation: str, this: SetVar, other: Any) -> None:
    """Reject an operand that is not a set or an array.

    Args:
        operation: The name of the operation, for the error message.
        this: The set var the operation is called on.
        other: The operand to check.
    """
    if not isinstance(other, (SetVar, ArrayVar, *_OTHER_SET_TYPES)):
        raise_unsupported_operand_types(operation, (type(this), type(other)))


class SetVar(Var[SET_VAR_TYPE], python_types=(set, frozenset)):
    """Base class for immutable set vars."""

    def contains(self, other: Any) -> BooleanVar:
        """Check if the set contains an element.

        Args:
            other: The element to check for.

        Returns:
            Whether the set contains the element.
        """
        return set_contains_operation(self, other)

    has = contains

    def length(self) -> NumberVar[int]:
        """Get the number of elements in the set.

        Returns:
            The number of elements.
        """
        return set_length_operation(self)

    size = length

    def union(self, other: Any) -> SetVar[SET_VAR_TYPE]:
        """Get the elements in this set or the other.

        Args:
            other: The other set or array.

        Returns:
            The union of the two sets.
        """
        _check_other("union", self, other)
        return set_union_operation(self, other)

    def intersection(self, other: Any) -> SetVar[SET_VAR_TYPE]:
        """Get the elements in both this set and the other.

        Args:
            other: The other set or array.

        Returns:
            The intersection of the two sets.
        """
        _check_other("intersection", self, other)
        return set_intersection_operation(self, other)

    def difference(self, other: Any) -> SetVar[SET_VAR_TYPE]:
        """Get the elements in this set but not in the other.

        Args:
            other: The other set or array.

        Returns:
            The difference of the two sets.
        """
        _check_other("difference", self, other)
        return set_difference_operation(self, other)

    def symmetric_difference(self, other: Any) -> SetVar[SET_VAR_TYPE]:
        """Get the elements in exactly one of this set and the other.

        Args:
            other: The other set or array.

        Returns:
            The symmetric difference of the two sets.
        """
        _check_other("symmetric_difference", self, other)
        return set_symmetric_difference_operation(self, other)

    def issubset(self, other: Any) -> BooleanVar:
        """Check if every element of this set is in the other.

        Args:
            other: The other set or array.

        Returns:
            Whether this set is a subset of the other.
        """
        _check_other("issubset", self, other)
        return set_issubset_operation(self, other)

    def issuperset(self, other: Any) -> BooleanVar:
        """Check if every element of the other is in this set.

        Args:
            other: The other set or array.

        Returns:
            Whether this set is a superset of the other.
        """
        _check_other("issuperset", self, other)
        return set_issuperset_operation(self, other)

    def isdisjoint(self, other: Any) -> BooleanVar:
        """Check if this set and the other have no element in common.

        Args:
            other: The other set or array.

        Returns:
            Whether the two sets are disjoint.
        """
        _check_other("isdisjoint", self, other)
        return set_isdisjoint_operation(self, other)

    @overload
    def to_array(
        self: SetVar[set[SET_ELEMENT]] | SetVar[frozenset[SET_ELEMENT]],
    ) -> ArrayVar[Sequence[SET_ELEMENT]]: ...

    @overload
    def to_array(self) -> ArrayVar[Sequence[Any]]: ...

    def to_array(self) -> ArrayVar:
        """View the set as an array, for rx.foreach and array operations.

        The frontend value is already an array, so this only changes the type.

        Returns:
            The set as an array var.
        """
        return self.to(ArrayVar, Sequence[_element_type(self._var_type)])

    if TYPE_CHECKING:

        @deprecated(_ARRAY_OPERATION_REASON)
        def __getitem__(self, i: Any) -> Var:
            """Index the set as an array (deprecated, use to_array).

            Args:
                i: The index or slice.

            Returns:
                The element or slice.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def __add__(self, other: Any) -> ArrayVar:
            """Concatenate the set as an array (deprecated, use to_array).

            Args:
                other: The other array.

            Returns:
                The concatenated array.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def __mul__(self, other: Any) -> ArrayVar:
            """Repeat the set as an array (deprecated, use to_array).

            Args:
                other: The number of repetitions.

            Returns:
                The repeated array.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def join(self, sep: Any = "") -> Var:
            """Join the set as an array (deprecated, use to_array).

            Args:
                sep: The separator between elements.

            Returns:
                The joined string.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def reverse(self) -> ArrayVar:
            """Reverse the set as an array (deprecated, use to_array).

            Returns:
                The reversed array.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def pluck(self, field: Any) -> ArrayVar:
            """Pluck a field from the set as an array (deprecated, use to_array).

            Args:
                field: The field to pluck.

            Returns:
                The plucked array.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def map(self, fn: Any) -> Var:
            """Map over the set as an array (deprecated, use to_array).

            Args:
                fn: The function to apply.

            Returns:
                The mapped array.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def foreach(self, fn: Any) -> Var:
            """Map over the set as an array (deprecated, use to_array).

            Args:
                fn: The function to apply.

            Returns:
                The mapped array.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def filter(self, fn: Any = None) -> ArrayVar:
            """Filter the set as an array (deprecated, use to_array).

            Args:
                fn: The predicate.

            Returns:
                The filtered array.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def reduce(self, fn: Any, initial: Any = ...) -> Var:
            """Reduce the set as an array (deprecated, use to_array).

            Args:
                fn: The reducer.
                initial: The initial accumulator.

            Returns:
                The reduced value.
            """
            ...

        @deprecated(_ARRAY_OPERATION_REASON)
        def flat_map(self, fn: Any) -> Var:
            """Flat-map over the set as an array (deprecated, use to_array).

            Args:
                fn: The function to apply.

            Returns:
                The flattened array.
            """
            ...

    else:
        __getitem__ = _deprecated_array_operation("__getitem__")
        __add__ = _deprecated_array_operation("__add__")
        __mul__ = _deprecated_array_operation("__mul__")
        __rmul__ = __mul__
        join = _deprecated_array_operation("join")
        reverse = _deprecated_array_operation("reverse")
        pluck = _deprecated_array_operation("pluck")
        map = _deprecated_array_operation("map")
        foreach = _deprecated_array_operation("foreach")
        filter = _deprecated_array_operation("filter")
        reduce = _deprecated_array_operation("reduce")
        flat_map = _deprecated_array_operation("flat_map")


@var_operation
def set_contains_operation(
    haystack: SetVar, needle: Any | Var
) -> CustomVarOperationReturn[bool]:
    """Check if a set contains an element.

    Args:
        haystack: The set to check.
        needle: The element to check for.

    Returns:
        The set contains operation.
    """
    return var_operation_return(
        js_expression=f"{haystack!s}.includes({needle!s})",
        var_type=bool,
    )


@var_operation
def set_length_operation(value: SetVar) -> CustomVarOperationReturn[int]:
    """Get the number of elements in a set.

    Args:
        value: The set.

    Returns:
        The set length operation.
    """
    return var_operation_return(js_expression=f"{value!s}.length", var_type=int)


@var_operation
def set_union_operation(
    lhs: SetVar[SET_VAR_TYPE], rhs: SetVar | ArrayVar
) -> CustomVarOperationReturn[SET_VAR_TYPE]:
    """Get the union of two sets.

    Args:
        lhs: The left-hand side set.
        rhs: The right-hand side set or array.

    Returns:
        The set union operation.
    """
    return var_operation_return(
        js_expression=f"[...new Set([...{lhs!s}, ...{rhs!s}])]",
        var_type=_set_type_like(
            lhs._var_type,
            unionize(_element_type(lhs._var_type), _element_type(rhs._var_type)),
        ),
    )


@var_operation
def set_intersection_operation(
    lhs: SetVar[SET_VAR_TYPE], rhs: SetVar | ArrayVar
) -> CustomVarOperationReturn[SET_VAR_TYPE]:
    """Get the intersection of two sets.

    Args:
        lhs: The left-hand side set.
        rhs: The right-hand side set or array.

    Returns:
        The set intersection operation.
    """
    return var_operation_return(
        js_expression=f"((a, b) => a.filter((x) => b.has(x)))({lhs!s}, new Set({rhs!s}))",
        var_type=lhs._var_type,
    )


@var_operation
def set_difference_operation(
    lhs: SetVar[SET_VAR_TYPE], rhs: SetVar | ArrayVar
) -> CustomVarOperationReturn[SET_VAR_TYPE]:
    """Get the elements of a set that are not in another.

    Args:
        lhs: The left-hand side set.
        rhs: The right-hand side set or array.

    Returns:
        The set difference operation.
    """
    return var_operation_return(
        js_expression=f"((a, b) => a.filter((x) => !b.has(x)))({lhs!s}, new Set({rhs!s}))",
        var_type=lhs._var_type,
    )


@var_operation
def set_symmetric_difference_operation(
    lhs: SetVar[SET_VAR_TYPE], rhs: SetVar | ArrayVar
) -> CustomVarOperationReturn[SET_VAR_TYPE]:
    """Get the elements in exactly one of two sets.

    Args:
        lhs: The left-hand side set.
        rhs: The right-hand side set or array.

    Returns:
        The set symmetric difference operation.
    """
    return var_operation_return(
        js_expression=(
            "((a, b) => [...[...a].filter((x) => !b.has(x)), ...[...b].filter((x) => !a.has(x))])"
            f"(new Set({lhs!s}), new Set({rhs!s}))"
        ),
        var_type=_set_type_like(
            lhs._var_type,
            unionize(_element_type(lhs._var_type), _element_type(rhs._var_type)),
        ),
    )


@var_operation
def set_issubset_operation(
    lhs: SetVar, rhs: SetVar | ArrayVar
) -> CustomVarOperationReturn[bool]:
    """Check if every element of a set is in another.

    Args:
        lhs: The left-hand side set.
        rhs: The right-hand side set or array.

    Returns:
        The set issubset operation.
    """
    return var_operation_return(
        js_expression=f"((a, b) => a.every((x) => b.has(x)))({lhs!s}, new Set({rhs!s}))",
        var_type=bool,
    )


@var_operation
def set_issuperset_operation(
    lhs: SetVar, rhs: SetVar | ArrayVar
) -> CustomVarOperationReturn[bool]:
    """Check if a set contains every element of another.

    Args:
        lhs: The left-hand side set.
        rhs: The right-hand side set or array.

    Returns:
        The set issuperset operation.
    """
    return var_operation_return(
        js_expression=f"((a, b) => b.every((x) => a.has(x)))(new Set({lhs!s}), {rhs!s})",
        var_type=bool,
    )


@var_operation
def set_isdisjoint_operation(
    lhs: SetVar, rhs: SetVar | ArrayVar
) -> CustomVarOperationReturn[bool]:
    """Check if two sets have no element in common.

    Args:
        lhs: The left-hand side set.
        rhs: The right-hand side set or array.

    Returns:
        The set isdisjoint operation.
    """
    return var_operation_return(
        js_expression=f"((a, b) => !a.some((x) => b.has(x)))({lhs!s}, new Set({rhs!s}))",
        var_type=bool,
    )


def _ordered(value: set | frozenset) -> list:
    """Order the elements of a set literal, so it compiles the same way every run.

    Args:
        value: The set to order.

    Returns:
        The sorted elements, or the set's own order when they do not compare.
    """
    try:
        return sorted(value)
    except TypeError:
        return list(value)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralSetVar(CachedVarOperation, LiteralVar[SET_VAR_TYPE], SetVar[SET_VAR_TYPE]):
    """Base class for immutable literal set vars."""

    _var_value: set[Var | Any] | frozenset[Var | Any] = dataclasses.field(
        default_factory=frozenset
    )

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "["
            + ", ".join([
                str(LiteralVar.create(element)) for element in _ordered(self._var_value)
            ])
            + "]"
        )

    @classmethod
    def _get_all_var_data_without_creating_var(
        cls, value: set | frozenset
    ) -> VarData | None:
        """Get all the VarData associated with the Var without creating a Var.

        Args:
            value: The value to get the VarData for.

        Returns:
            The VarData associated with the Var.
        """
        return _literal_elements_var_data(value)

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the VarData associated with the Var.

        Returns:
            The VarData associated with the Var.
        """
        return VarData.merge(
            _literal_elements_var_data(self._var_value), self._var_data
        )

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.
        """
        return _literal_elements_json(_ordered(self._var_value))

    @classmethod
    def create(
        cls,
        value: OTHER_SET_VAR_TYPE,
        _var_type: type[OTHER_SET_VAR_TYPE] | None = None,
        _var_data: VarData | None = None,
    ) -> LiteralSetVar[OTHER_SET_VAR_TYPE]:
        """Create a var from a set value.

        Args:
            value: The value to create the var from.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return LiteralSetVar(
            _js_expr="",
            _var_type=figure_out_type(value) if _var_type is None else _var_type,
            _var_data=_var_data,
            _var_value=value,
        )
