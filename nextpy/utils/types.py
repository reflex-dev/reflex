"""Contains custom types and methods to check types."""

from __future__ import annotations

import contextlib
import types
from typing import (
    Any,
    Callable,
    Iterable,
    Literal,
    Optional,
    Type,
    Union,
    _GenericAlias,  # type: ignore
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic.fields import ModelField
from nextpy.core.base import Base
from nextpy.utils import serializers

# Union of generic types.
GenericType = Union[Type, _GenericAlias]

# Valid state var types.
PrimitiveType = Union[int, float, bool, str, list, dict, set, tuple]
StateVar = Union[PrimitiveType, Base, None]
StateIterVar = Union[list, set, tuple]

# ArgsSpec = Callable[[Var], list[Var]]
ArgsSpec = Callable


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
    # UnionType added in py3.10
    if not hasattr(types, "UnionType"):
        return get_origin(cls) is Union

    return get_origin(cls) in [Union, types.UnionType]


def is_literal(cls: GenericType) -> bool:
    """Check if a class is a Literal.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a literal.
    """
    return get_origin(cls) is Literal


def is_optional(cls: GenericType) -> bool:
    """Check if a class is an Optional.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is an Optional.
    """
    return is_union(cls) and type(None) in get_args(cls)


def get_attribute_access_type(cls: GenericType, name: str) -> GenericType | None:
    """Check if an attribute can be accessed on the cls and return its type.

    Supports pydantic models, unions, and annotated attributes on xt.Model.

    Args:
        cls: The class to check.
        name: The name of the attribute to check.

    Returns:
        The type of the attribute, if accessible, or None
    """
    from nextpy.core.model import Model

    if hasattr(cls, "__fields__") and name in cls.__fields__:
        # pydantic models
        field = cls.__fields__[name]
        type_ = field.outer_type_
        if isinstance(type_, ModelField):
            type_ = type_.type_
        if not field.required and field.default is None:
            # Ensure frontend uses null coalescing when accessing.
            type_ = Optional[type_]
        return type_
    elif isinstance(cls, type) and issubclass(cls, Model):
        # Check in the annotations directly (for sqlmodel.Relationship)
        hints = get_type_hints(cls)
        if name in hints:
            type_ = hints[name]
            if isinstance(type_, ModelField):
                return type_.type_
            return type_
    elif is_union(cls):
        # Check in each arg of the annotation.
        for arg in get_args(cls):
            type_ = get_attribute_access_type(arg, name)
            if type_ is not None:
                # Return the first attribute type that is accessible.
                return type_
    return None  # Attribute is not accessible.


def get_base_class(cls: GenericType) -> Type:
    """Get the base class of a class.

    Args:
        cls: The class.

    Returns:
        The base class of the class.

    Raises:
        TypeError: If a literal has multiple types.
    """
    if is_literal(cls):
        # only literals of the same type are supported.
        arg_type = type(get_args(cls)[0])
        if not all(type(arg) == arg_type for arg in get_args(cls)):
            raise TypeError("only literals of the same type are supported")
        return type(get_args(cls)[0])

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
    if is_generic_alias(value) or value == Any:
        return False
    return value.__name__ == "DataFrame"


def is_valid_var_type(type_: Type) -> bool:
    """Check if the given type is a valid prop type.

    Args:
        type_: The type to check.

    Returns:
        Whether the type is a valid prop type.
    """
    if is_union(type_):
        return all((is_valid_var_type(arg) for arg in get_args(type_)))
    return _issubclass(type_, StateVar) or serializers.has_serializer(type_)


def is_backend_variable(name: str) -> bool:
    """Check if this variable name correspond to a backend variable.

    Args:
        name: The name of the variable to check

    Returns:
        bool: The result of the check
    """
    return name.startswith("_") and not name.startswith("__")


def check_type_in_allowed_types(value_type: Type, allowed_types: Iterable) -> bool:
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
