"""Contains custom types and methods to check types."""

from __future__ import annotations

import contextlib
import typing
from typing import Any, Callable, Type, Union, _GenericAlias  # type: ignore

from reflex.base import Base
from reflex.utils import serializers

# Union of generic types.
GenericType = Union[Type, _GenericAlias]

# Valid state var types.
PrimitiveType = Union[int, float, bool, str, list, dict, set, tuple]
StateVar = Union[PrimitiveType, Base, None]
StateIterVar = Union[list, set, tuple]

# ArgsSpec = Callable[[Var], list[Var]]
ArgsSpec = Callable


def get_args(alias: _GenericAlias) -> tuple[Type, ...]:
    """Get the arguments of a type alias.

    Args:
        alias: The type alias.

    Returns:
        The arguments of the type alias.
    """
    return alias.__args__


def is_generic_alias(cls: GenericType) -> bool:
    """Check whether the class is a generic alias.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a generic alias.
    """
    # For older versions of Python.
    if isinstance(cls, _GenericAlias):
        return True

    with contextlib.suppress(ImportError):
        from typing import _SpecialGenericAlias  # type: ignore

        if isinstance(cls, _SpecialGenericAlias):
            return True
    # For newer versions of Python.
    try:
        from types import GenericAlias  # type: ignore

        return isinstance(cls, GenericAlias)
    except ImportError:
        return False


def is_union(cls: GenericType) -> bool:
    """Check if a class is a Union.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a Union.
    """
    with contextlib.suppress(ImportError):
        from typing import _UnionGenericAlias  # type: ignore

        return isinstance(cls, _UnionGenericAlias)
    return cls.__origin__ == Union if is_generic_alias(cls) else False


def get_base_class(cls: GenericType) -> Type:
    """Get the base class of a class.

    Args:
        cls: The class.

    Returns:
        The base class of the class.
    """
    if is_union(cls):
        return tuple(get_base_class(arg) for arg in get_args(cls))

    return get_base_class(cls.__origin__) if is_generic_alias(cls) else cls


def _issubclass(cls: GenericType, cls_check: GenericType) -> bool:
    """Check if a class is a subclass of another class.

    Args:
        cls: The class to check.
        cls_check: The class to check against.

    Returns:
        Whether the class is a subclass of the other class.

    Raises:
        TypeError: If the base class is not valid for issubclass.
    """
    # Special check for Any.
    if cls_check == Any:
        return True
    if cls in [Any, Callable, None]:
        return False

    # Get the base classes.
    cls_base = get_base_class(cls)
    cls_check_base = get_base_class(cls_check)

    # The class we're checking should not be a union.
    if isinstance(cls_base, tuple):
        return False

    # Check if the types match.
    try:
        return cls_check_base == Any or issubclass(cls_base, cls_check_base)
    except TypeError as te:
        # These errors typically arise from bad annotations and are hard to
        # debug without knowing the type that we tried to compare.
        raise TypeError(f"Invalid type for issubclass: {cls_base}") from te


def _isinstance(obj: Any, cls: GenericType) -> bool:
    """Check if an object is an instance of a class.

    Args:
        obj: The object to check.
        cls: The class to check against.

    Returns:
        Whether the object is an instance of the class.
    """
    return isinstance(obj, get_base_class(cls))


def is_dataframe(value: Type) -> bool:
    """Check if the given value is a dataframe.

    Args:
        value: The value to check.

    Returns:
        Whether the value is a dataframe.
    """
    if is_generic_alias(value) or value == typing.Any:
        return False
    return value.__name__ == "DataFrame"


def is_valid_var_type(type_: Type) -> bool:
    """Check if the given type is a valid prop type.

    Args:
        type_: The type to check.

    Returns:
        Whether the type is a valid prop type.
    """
    return _issubclass(type_, StateVar) or serializers.has_serializer(type_)


def is_backend_variable(name: str) -> bool:
    """Check if this variable name correspond to a backend variable.

    Args:
        name: The name of the variable to check

    Returns:
        bool: The result of the check
    """
    return name.startswith("_") and not name.startswith("__")


def check_type_in_allowed_types(
    value_type: Type, allowed_types: typing.Iterable
) -> bool:
    """Check that a value type is found in a list of allowed types.

    Args:
        value_type: Type of value.
        allowed_types: Iterable of allowed types.

    Returns:
        If the type is found in the allowed types.
    """
    return get_base_class(value_type) in allowed_types


# Store this here for performance.
StateBases = get_base_class(StateVar)
StateIterBases = get_base_class(StateIterVar)
