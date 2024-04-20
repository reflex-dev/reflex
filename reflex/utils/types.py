"""Contains custom types and methods to check types."""

from __future__ import annotations

import contextlib
import inspect
import types
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    List,
    Literal,
    Optional,
    Type,
    Union,
    _GenericAlias,  # type: ignore
    get_args,
    get_origin,
    get_type_hints,
)

import sqlalchemy

try:
    # TODO The type checking guard can be removed once
    # reflex-hosting-cli tools are compatible with pydantic v2

    if not TYPE_CHECKING:
        from pydantic.v1.fields import ModelField
    else:
        raise ModuleNotFoundError
except ModuleNotFoundError:
    from pydantic.fields import ModelField

from sqlalchemy.ext.associationproxy import AssociationProxyInstance
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, QueryableAttribute, Relationship

from reflex import constants
from reflex.base import Base
from reflex.utils import serializers

# Potential GenericAlias types for isinstance checks.
GenericAliasTypes = [_GenericAlias]

with contextlib.suppress(ImportError):
    # For newer versions of Python.
    from types import GenericAlias  # type: ignore

    GenericAliasTypes.append(GenericAlias)

with contextlib.suppress(ImportError):
    # For older versions of Python.
    from typing import _SpecialGenericAlias  # type: ignore

    GenericAliasTypes.append(_SpecialGenericAlias)

GenericAliasTypes = tuple(GenericAliasTypes)

# Potential Union types for isinstance checks (UnionType added in py3.10).
UnionTypes = (Union, types.UnionType) if hasattr(types, "UnionType") else (Union,)

# Union of generic types.
GenericType = Union[Type, _GenericAlias]

# Valid state var types.
JSONType = {str, int, float, bool}
PrimitiveType = Union[int, float, bool, str, list, dict, set, tuple]
StateVar = Union[PrimitiveType, Base, None]
StateIterVar = Union[list, set, tuple]

# ArgsSpec = Callable[[Var], list[Var]]
ArgsSpec = Callable


class Unset:
    """A class to represent an unset value.

    This is used to differentiate between a value that is not set and a value that is set to None.
    """

    def __repr__(self) -> str:
        """Return the string representation of the class.

        Returns:
            The string representation of the class.
        """
        return "Unset"

    def __bool__(self) -> bool:
        """Return False when the class is used in a boolean context.

        Returns:
            False
        """
        return False


def is_generic_alias(cls: GenericType) -> bool:
    """Check whether the class is a generic alias.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a generic alias.
    """
    return isinstance(cls, GenericAliasTypes)


def is_union(cls: GenericType) -> bool:
    """Check if a class is a Union.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a Union.
    """
    return get_origin(cls) in UnionTypes


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


def get_property_hint(attr: Any | None) -> GenericType | None:
    """Check if an attribute is a property and return its type hint.

    Args:
        attr: The descriptor to check.

    Returns:
        The type hint of the property, if it is a property, else None.
    """
    if not isinstance(attr, (property, hybrid_property)):
        return None
    hints = get_type_hints(attr.fget)
    return hints.get("return", None)


def get_attribute_access_type(cls: GenericType, name: str) -> GenericType | None:
    """Check if an attribute can be accessed on the cls and return its type.

    Supports pydantic models, unions, and annotated attributes on rx.Model.

    Args:
        cls: The class to check.
        name: The name of the attribute to check.

    Returns:
        The type of the attribute, if accessible, or None
    """
    from reflex.model import Model

    attr = getattr(cls, name, None)
    if hint := get_property_hint(attr):
        return hint
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
    elif isinstance(cls, type) and issubclass(cls, DeclarativeBase):
        insp = sqlalchemy.inspect(cls)
        if name in insp.columns:
            return insp.columns[name].type.python_type
        if name not in insp.all_orm_descriptors.keys():
            return None
        descriptor = insp.all_orm_descriptors[name]
        if hint := get_property_hint(descriptor):
            return hint
        if isinstance(descriptor, QueryableAttribute):
            prop = descriptor.property
            if not isinstance(prop, Relationship):
                return None
            class_ = prop.mapper.class_
            if prop.uselist:
                return List[class_]
            else:
                return class_
        if isinstance(attr, AssociationProxyInstance):
            return List[
                get_attribute_access_type(
                    attr.target_class,
                    attr.remote_attr.key,  # type: ignore[attr-defined]
                )
            ]
    elif isinstance(cls, type) and not is_generic_alias(cls) and issubclass(cls, Model):
        # Check in the annotations directly (for sqlmodel.Relationship)
        hints = get_type_hints(cls)
        if name in hints:
            type_ = hints[name]
            type_origin = get_origin(type_)
            if isinstance(type_origin, type) and issubclass(type_origin, Mapped):
                return get_args(type_)[0]  # SQLAlchemy v2
            if isinstance(type_, ModelField):
                return type_.type_  # SQLAlchemy v1.4
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


def is_backend_variable(name: str, cls: Type | None = None) -> bool:
    """Check if this variable name correspond to a backend variable.

    Args:
        name: The name of the variable to check
        cls: The class of the variable to check

    Returns:
        bool: The result of the check
    """
    if cls is not None and name.startswith(f"_{cls.__name__}__"):
        return False
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


def check_prop_in_allowed_types(prop: Any, allowed_types: Iterable) -> bool:
    """Check that a prop value is in a list of allowed types.
    Does the check in a way that works regardless if it's a raw value or a state Var.

    Args:
        prop: The prop to check.
        allowed_types: The list of allowed types.

    Returns:
        If the prop type match one of the allowed_types.
    """
    from reflex.vars import Var

    type_ = prop._var_type if _isinstance(prop, Var) else type(prop)
    return type_ in allowed_types


def is_encoded_fstring(value) -> bool:
    """Check if a value is an encoded Var f-string.

    Args:
        value: The value string to check.

    Returns:
        Whether the value is an f-string
    """
    return isinstance(value, str) and constants.REFLEX_VAR_OPENING_TAG in value


def validate_literal(key: str, value: Any, expected_type: Type, comp_name: str):
    """Check that a value is a valid literal.

    Args:
        key: The prop name.
        value: The prop value to validate.
        expected_type: The expected type(literal type).
        comp_name: Name of the component.

    Raises:
        ValueError: When the value is not a valid literal.
    """
    from reflex.vars import Var

    if (
        is_literal(expected_type)
        and not isinstance(value, Var)  # validating vars is not supported yet.
        and not is_encoded_fstring(value)  # f-strings are not supported.
        and value not in expected_type.__args__
    ):
        allowed_values = expected_type.__args__
        if value not in allowed_values:
            allowed_value_str = ",".join(
                [str(v) if not isinstance(v, str) else f"'{v}'" for v in allowed_values]
            )
            value_str = f"'{value}'" if isinstance(value, str) else value
            raise ValueError(
                f"prop value for {str(key)} of the `{comp_name}` component should be one of the following: {allowed_value_str}. Got {value_str} instead"
            )


def validate_parameter_literals(func):
    """Decorator to check that the arguments passed to a function
    correspond to the correct function parameter if it (the parameter)
    is a literal type.

    Args:
        func: The function to validate.

    Returns:
        The wrapper function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        func_params = list(inspect.signature(func).parameters.items())
        annotations = {param[0]: param[1].annotation for param in func_params}

        # validate args
        for param, arg in zip(annotations.keys(), args):
            if annotations[param] is inspect.Parameter.empty:
                continue
            validate_literal(param, arg, annotations[param], func.__name__)

        # validate kwargs.
        for key, value in kwargs.items():
            annotation = annotations.get(key)
            if not annotation or annotation is inspect.Parameter.empty:
                continue
            validate_literal(key, value, annotation, func.__name__)
        return func(*args, **kwargs)

    return wrapper


# Store this here for performance.
StateBases = get_base_class(StateVar)
StateIterBases = get_base_class(StateIterVar)
