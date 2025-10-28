"""Contains custom types and methods to check types."""

from __future__ import annotations

import dataclasses
import sys
import types
from collections.abc import Callable, Iterable, Mapping, Sequence
from enum import Enum
from functools import cached_property, lru_cache
from importlib.util import find_spec
from types import GenericAlias
from typing import (  # noqa: UP035
    TYPE_CHECKING,
    Any,
    Awaitable,
    ClassVar,
    Dict,
    ForwardRef,
    List,
    Literal,
    MutableMapping,
    NoReturn,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    _eval_type,  # pyright: ignore [reportAttributeAccessIssue]
    _GenericAlias,  # pyright: ignore [reportAttributeAccessIssue]
    _SpecialGenericAlias,  # pyright: ignore [reportAttributeAccessIssue]
    get_args,
    is_typeddict,
)
from typing import get_origin as get_origin_og
from typing import get_type_hints as get_type_hints_og

from typing_extensions import Self as Self
from typing_extensions import override as override

import reflex
from reflex import constants
from reflex.base import Base
from reflex.components.core.breakpoints import Breakpoints
from reflex.utils import console

# Potential GenericAlias types for isinstance checks.
GenericAliasTypes = (_GenericAlias, GenericAlias, _SpecialGenericAlias)

# Potential Union types for isinstance checks.
UnionTypes = (Union, types.UnionType)

# Union of generic types.
GenericType = type | _GenericAlias

# Valid state var types.
PrimitiveTypes = (int, float, bool, str, list, dict, set, tuple)
StateVarTypes = (*PrimitiveTypes, Base, type(None))

if TYPE_CHECKING:
    from reflex.vars.base import Var

VAR1 = TypeVar("VAR1", bound="Var")
VAR2 = TypeVar("VAR2", bound="Var")
VAR3 = TypeVar("VAR3", bound="Var")
VAR4 = TypeVar("VAR4", bound="Var")
VAR5 = TypeVar("VAR5", bound="Var")
VAR6 = TypeVar("VAR6", bound="Var")
VAR7 = TypeVar("VAR7", bound="Var")


class _ArgsSpec0(Protocol):
    def __call__(self) -> Sequence[Var]: ...


class _ArgsSpec1(Protocol):
    def __call__(self, var1: VAR1, /) -> Sequence[Var]: ...  # pyright: ignore [reportInvalidTypeVarUse]


class _ArgsSpec2(Protocol):
    def __call__(self, var1: VAR1, var2: VAR2, /) -> Sequence[Var]: ...  # pyright: ignore [reportInvalidTypeVarUse]


class _ArgsSpec3(Protocol):
    def __call__(self, var1: VAR1, var2: VAR2, var3: VAR3, /) -> Sequence[Var]: ...  # pyright: ignore [reportInvalidTypeVarUse]


class _ArgsSpec4(Protocol):
    def __call__(
        self,
        var1: VAR1,  # pyright: ignore [reportInvalidTypeVarUse]
        var2: VAR2,  # pyright: ignore [reportInvalidTypeVarUse]
        var3: VAR3,  # pyright: ignore [reportInvalidTypeVarUse]
        var4: VAR4,  # pyright: ignore [reportInvalidTypeVarUse]
        /,
    ) -> Sequence[Var]: ...


class _ArgsSpec5(Protocol):
    def __call__(
        self,
        var1: VAR1,  # pyright: ignore [reportInvalidTypeVarUse]
        var2: VAR2,  # pyright: ignore [reportInvalidTypeVarUse]
        var3: VAR3,  # pyright: ignore [reportInvalidTypeVarUse]
        var4: VAR4,  # pyright: ignore [reportInvalidTypeVarUse]
        var5: VAR5,  # pyright: ignore [reportInvalidTypeVarUse]
        /,
    ) -> Sequence[Var]: ...


class _ArgsSpec6(Protocol):
    def __call__(
        self,
        var1: VAR1,  # pyright: ignore [reportInvalidTypeVarUse]
        var2: VAR2,  # pyright: ignore [reportInvalidTypeVarUse]
        var3: VAR3,  # pyright: ignore [reportInvalidTypeVarUse]
        var4: VAR4,  # pyright: ignore [reportInvalidTypeVarUse]
        var5: VAR5,  # pyright: ignore [reportInvalidTypeVarUse]
        var6: VAR6,  # pyright: ignore [reportInvalidTypeVarUse]
        /,
    ) -> Sequence[Var]: ...


class _ArgsSpec7(Protocol):
    def __call__(
        self,
        var1: VAR1,  # pyright: ignore [reportInvalidTypeVarUse]
        var2: VAR2,  # pyright: ignore [reportInvalidTypeVarUse]
        var3: VAR3,  # pyright: ignore [reportInvalidTypeVarUse]
        var4: VAR4,  # pyright: ignore [reportInvalidTypeVarUse]
        var5: VAR5,  # pyright: ignore [reportInvalidTypeVarUse]
        var6: VAR6,  # pyright: ignore [reportInvalidTypeVarUse]
        var7: VAR7,  # pyright: ignore [reportInvalidTypeVarUse]
        /,
    ) -> Sequence[Var]: ...


ArgsSpec = (
    _ArgsSpec0
    | _ArgsSpec1
    | _ArgsSpec2
    | _ArgsSpec3
    | _ArgsSpec4
    | _ArgsSpec5
    | _ArgsSpec6
    | _ArgsSpec7
)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

PrimitiveToAnnotation = {
    list: List,  # noqa: UP006
    tuple: Tuple,  # noqa: UP006
    dict: Dict,  # noqa: UP006
}

RESERVED_BACKEND_VAR_NAMES = {"_abc_impl", "_backend_vars", "_was_touched", "_mixin"}


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


@lru_cache
def _get_origin_cached(tp: Any):
    return get_origin_og(tp)


def get_origin(tp: Any):
    """Get the origin of a class.

    Args:
        tp: The class to get the origin of.

    Returns:
        The origin of the class.
    """
    return (
        origin
        if (origin := getattr(tp, "__origin__", None)) is not None
        else _get_origin_cached(tp)
    )


@lru_cache
def is_generic_alias(cls: GenericType) -> bool:
    """Check whether the class is a generic alias.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a generic alias.
    """
    return isinstance(cls, GenericAliasTypes)


@lru_cache
def get_type_hints(obj: Any) -> dict[str, Any]:
    """Get the type hints of a class.

    Args:
        obj: The class to get the type hints of.

    Returns:
        The type hints of the class.
    """
    return get_type_hints_og(obj)


def _unionize(args: list[GenericType]) -> GenericType:
    if not args:
        return Any  # pyright: ignore [reportReturnType]
    if len(args) == 1:
        return args[0]
    return Union[tuple(args)]  # noqa: UP007


def unionize(*args: GenericType) -> type:
    """Unionize the types.

    Args:
        args: The types to unionize.

    Returns:
        The unionized types.
    """
    return _unionize([arg for arg in args if arg is not NoReturn])


def is_none(cls: GenericType) -> bool:
    """Check if a class is None.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is None.
    """
    return cls is type(None) or cls is None


def is_union(cls: GenericType) -> bool:
    """Check if a class is a Union.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a Union.
    """
    origin = getattr(cls, "__origin__", None)
    if origin is Union:
        return True
    return origin is None and isinstance(cls, types.UnionType)


def is_literal(cls: GenericType) -> bool:
    """Check if a class is a Literal.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a literal.
    """
    return getattr(cls, "__origin__", None) is Literal


@lru_cache
def has_args(cls: type) -> bool:
    """Check if the class has generic parameters.

    Args:
        cls: The class to check.

    Returns:
        Whether the class has generic
    """
    if get_args(cls):
        return True

    # Check if the class inherits from a generic class (using __orig_bases__)
    if hasattr(cls, "__orig_bases__"):
        for base in cls.__orig_bases__:
            if get_args(base):
                return True

    return False


def is_optional(cls: GenericType) -> bool:
    """Check if a class is an Optional.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is an Optional.
    """
    return (
        cls is None
        or cls is type(None)
        or (is_union(cls) and type(None) in get_args(cls))
    )


def is_classvar(a_type: Any) -> bool:
    """Check if a type is a ClassVar.

    Args:
        a_type: The type to check.

    Returns:
        Whether the type is a ClassVar.
    """
    return (
        a_type is ClassVar
        or (type(a_type) is _GenericAlias and a_type.__origin__ is ClassVar)
        or (
            type(a_type) is ForwardRef and a_type.__forward_arg__.startswith("ClassVar")
        )
    )


def value_inside_optional(cls: GenericType) -> GenericType:
    """Get the value inside an Optional type or the original type.

    Args:
        cls: The class to check.

    Returns:
        The value inside the Optional type or the original type.
    """
    if is_union(cls) and len(args := get_args(cls)) >= 2 and type(None) in args:
        if len(args) == 2:
            return args[0] if args[1] is type(None) else args[1]
        return unionize(*[arg for arg in args if arg is not type(None)])
    return cls


def get_field_type(cls: GenericType, field_name: str) -> GenericType | None:
    """Get the type of a field in a class.

    Args:
        cls: The class to check.
        field_name: The name of the field to check.

    Returns:
        The type of the field, if it exists, else None.
    """
    if (fields := getattr(cls, "_fields", None)) is not None and field_name in fields:
        return fields[field_name].annotated_type
    if (
        hasattr(cls, "__fields__")
        and field_name in cls.__fields__
        and hasattr(cls.__fields__[field_name], "annotation")
        and not isinstance(cls.__fields__[field_name].annotation, (str, ForwardRef))
    ):
        return cls.__fields__[field_name].annotation
    type_hints = get_type_hints(cls)
    return type_hints.get(field_name, None)


PROPERTY_CLASSES = (property,)
if find_spec("sqlalchemy") and find_spec("sqlalchemy.ext"):
    from sqlalchemy.ext.hybrid import hybrid_property

    PROPERTY_CLASSES += (hybrid_property,)


def get_property_hint(attr: Any | None) -> GenericType | None:
    """Check if an attribute is a property and return its type hint.

    Args:
        attr: The descriptor to check.

    Returns:
        The type hint of the property, if it is a property, else None.
    """
    if not isinstance(attr, PROPERTY_CLASSES):
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
    try:
        attr = getattr(cls, name, None)
    except NotImplementedError:
        attr = None

    if hint := get_property_hint(attr):
        return hint

    if hasattr(cls, "__fields__") and name in cls.__fields__:
        # pydantic models
        return get_field_type(cls, name)
    if find_spec("sqlalchemy") and find_spec("sqlalchemy.orm"):
        import sqlalchemy
        from sqlalchemy.ext.associationproxy import AssociationProxyInstance
        from sqlalchemy.orm import (
            DeclarativeBase,
            Mapped,
            QueryableAttribute,
            Relationship,
        )

        from reflex.model import Model

        if find_spec("sqlmodel"):
            from sqlmodel import SQLModel

            sqlmodel_types = (Model, SQLModel)
        else:
            sqlmodel_types = (Model,)

        if isinstance(cls, type) and issubclass(cls, DeclarativeBase):
            insp = sqlalchemy.inspect(cls)
            if name in insp.columns:
                # check for list types
                column = insp.columns[name]
                column_type = column.type
                try:
                    type_ = insp.columns[name].type.python_type
                except NotImplementedError:
                    type_ = None
                if type_ is not None:
                    if hasattr(column_type, "item_type"):
                        try:
                            item_type = column_type.item_type.python_type  # pyright: ignore [reportAttributeAccessIssue]
                        except NotImplementedError:
                            item_type = None
                        if item_type is not None:
                            if type_ in PrimitiveToAnnotation:
                                type_ = PrimitiveToAnnotation[type_]
                            type_ = type_[item_type]  # pyright: ignore [reportIndexIssue]
                    if hasattr(column, "nullable") and column.nullable:
                        type_ = type_ | None
                    return type_
            if name in insp.all_orm_descriptors:
                descriptor = insp.all_orm_descriptors[name]
                if hint := get_property_hint(descriptor):
                    return hint
                if isinstance(descriptor, QueryableAttribute):
                    prop = descriptor.property
                    if isinstance(prop, Relationship):
                        type_ = prop.mapper.class_
                        # TODO: check for nullable?
                        return list[type_] if prop.uselist else type_ | None
                if isinstance(attr, AssociationProxyInstance):
                    return list[
                        get_attribute_access_type(
                            attr.target_class,
                            attr.remote_attr.key,  # pyright: ignore [reportAttributeAccessIssue]
                        )
                    ]
        elif (
            isinstance(cls, type)
            and not is_generic_alias(cls)
            and issubclass(cls, sqlmodel_types)
        ):
            # Check in the annotations directly (for sqlmodel.Relationship)
            hints = get_type_hints(cls)  # pyright: ignore [reportArgumentType]
            if name in hints:
                type_ = hints[name]
                type_origin = get_origin(type_)
                if isinstance(type_origin, type) and issubclass(type_origin, Mapped):
                    return get_args(type_)[0]  # SQLAlchemy v2
                if find_spec("pydantic"):
                    from pydantic.v1.fields import ModelField

                    if isinstance(type_, ModelField):
                        return type_.type_  # SQLAlchemy v1.4
                return type_
    if is_union(cls):
        # Check in each arg of the annotation.
        return unionize(
            *(get_attribute_access_type(arg, name) for arg in get_args(cls))
        )
    if isinstance(cls, type):
        # Bare class
        exceptions = NameError
        try:
            hints = get_type_hints(cls)  # pyright: ignore [reportArgumentType]
            if name in hints:
                return hints[name]
        except exceptions as e:
            console.warn(f"Failed to resolve ForwardRefs for {cls}.{name} due to {e}")
    return None  # Attribute is not accessible.


@lru_cache
def get_base_class(cls: GenericType) -> type:
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
        if not all(type(arg) is arg_type for arg in get_args(cls)):
            msg = "only literals of the same type are supported"
            raise TypeError(msg)
        return type(get_args(cls)[0])

    if is_union(cls):
        return tuple(get_base_class(arg) for arg in get_args(cls))  # pyright: ignore [reportReturnType]

    return get_base_class(cls.__origin__) if is_generic_alias(cls) else cls


def _breakpoints_satisfies_typing(cls_check: GenericType, instance: Any) -> bool:
    """Check if the breakpoints instance satisfies the typing.

    Args:
        cls_check: The class to check against.
        instance: The instance to check.

    Returns:
        Whether the breakpoints instance satisfies the typing.
    """
    cls_check_base = get_base_class(cls_check)

    if cls_check_base == Breakpoints:
        _, expected_type = get_args(cls_check)
        if is_literal(expected_type):
            for value in instance.values():
                if not isinstance(value, str) or value not in get_args(expected_type):
                    return False
        return True
    if isinstance(cls_check_base, tuple):
        # union type, so check all types
        return any(
            _breakpoints_satisfies_typing(type_to_check, instance)
            for type_to_check in get_args(cls_check)
        )
    if cls_check_base == reflex.vars.Var and "__args__" in cls_check.__dict__:
        return _breakpoints_satisfies_typing(get_args(cls_check)[0], instance)

    return False


def _issubclass(cls: GenericType, cls_check: GenericType, instance: Any = None) -> bool:
    """Check if a class is a subclass of another class.

    Args:
        cls: The class to check.
        cls_check: The class to check against.
        instance: An instance of cls to aid in checking generics.

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

    # Check that fields of breakpoints match the expected values.
    if isinstance(instance, Breakpoints):
        return _breakpoints_satisfies_typing(cls_check, instance)

    if isinstance(cls_check_base, tuple):
        cls_check_base = tuple(
            cls_check_one if not is_typeddict(cls_check_one) else dict
            for cls_check_one in cls_check_base
        )
    if is_typeddict(cls_check_base):
        cls_check_base = dict

    # Check if the types match.
    try:
        return cls_check_base == Any or issubclass(cls_base, cls_check_base)
    except TypeError as te:
        # These errors typically arise from bad annotations and are hard to
        # debug without knowing the type that we tried to compare.
        msg = f"Invalid type for issubclass: {cls_base}"
        raise TypeError(msg) from te


def does_obj_satisfy_typed_dict(
    obj: Any,
    cls: GenericType,
    *,
    nested: int = 0,
    treat_var_as_type: bool = True,
    treat_mutable_obj_as_immutable: bool = False,
) -> bool:
    """Check if an object satisfies a typed dict.

    Args:
        obj: The object to check.
        cls: The typed dict to check against.
        nested: How many levels deep to check.
        treat_var_as_type: Whether to treat Var as the type it represents, i.e. _var_type.
        treat_mutable_obj_as_immutable: Whether to treat mutable objects as immutable. Useful if a component declares a mutable object as a prop, but the value is not expected to change.

    Returns:
        Whether the object satisfies the typed dict.
    """
    if not isinstance(obj, Mapping):
        return False

    key_names_to_values = get_type_hints(cls)
    required_keys: frozenset[str] = getattr(cls, "__required_keys__", frozenset())
    is_closed = getattr(cls, "__closed__", False)
    extra_items_type = getattr(cls, "__extra_items__", Any)

    for key, value in obj.items():
        if is_closed and key not in key_names_to_values:
            return False
        if nested:
            if key in key_names_to_values:
                expected_type = key_names_to_values[key]
                if not _isinstance(
                    value,
                    expected_type,
                    nested=nested - 1,
                    treat_var_as_type=treat_var_as_type,
                    treat_mutable_obj_as_immutable=treat_mutable_obj_as_immutable,
                ):
                    return False
            else:
                if not _isinstance(
                    value,
                    extra_items_type,
                    nested=nested - 1,
                    treat_var_as_type=treat_var_as_type,
                    treat_mutable_obj_as_immutable=treat_mutable_obj_as_immutable,
                ):
                    return False

    # required keys are all present
    return required_keys.issubset(frozenset(obj))


def _isinstance(
    obj: Any,
    cls: GenericType,
    *,
    nested: int = 0,
    treat_var_as_type: bool = True,
    treat_mutable_obj_as_immutable: bool = False,
) -> bool:
    """Check if an object is an instance of a class.

    Args:
        obj: The object to check.
        cls: The class to check against.
        nested: How many levels deep to check.
        treat_var_as_type: Whether to treat Var as the type it represents, i.e. _var_type.
        treat_mutable_obj_as_immutable: Whether to treat mutable objects as immutable. Useful if a component declares a mutable object as a prop, but the value is not expected to change.

    Returns:
        Whether the object is an instance of the class.
    """
    if cls is Any:
        return True

    from reflex.vars import LiteralVar, Var

    if cls is Var:
        return isinstance(obj, Var)
    if isinstance(obj, LiteralVar):
        return treat_var_as_type and _isinstance(
            obj._var_value, cls, nested=nested, treat_var_as_type=True
        )
    if isinstance(obj, Var):
        return treat_var_as_type and typehint_issubclass(
            obj._var_type,
            cls,
            treat_mutable_superclasss_as_immutable=treat_mutable_obj_as_immutable,
            treat_literals_as_union_of_types=True,
            treat_any_as_subtype_of_everything=True,
        )

    if cls is None or cls is type(None):
        return obj is None

    if cls is not None and is_union(cls):
        return any(
            _isinstance(obj, arg, nested=nested, treat_var_as_type=treat_var_as_type)
            for arg in get_args(cls)
        )

    if is_literal(cls):
        return obj in get_args(cls)

    origin = get_origin(cls)

    if origin is None:
        # cls is a typed dict
        if is_typeddict(cls):
            if nested:
                return does_obj_satisfy_typed_dict(
                    obj,
                    cls,
                    nested=nested - 1,
                    treat_var_as_type=treat_var_as_type,
                    treat_mutable_obj_as_immutable=treat_mutable_obj_as_immutable,
                )
            return isinstance(obj, dict)

        # cls is a float
        if cls is float:
            return isinstance(obj, (float, int))

        # cls is a simple class
        return isinstance(obj, cls)

    args = get_args(cls)

    if not args:
        if treat_mutable_obj_as_immutable:
            if origin is dict:
                origin = Mapping
            elif origin is list or origin is set:
                origin = Sequence
        # cls is a simple generic class
        return isinstance(obj, origin)

    if origin is Var and args:
        # cls is a Var
        return _isinstance(
            obj,
            args[0],
            nested=nested,
            treat_var_as_type=treat_var_as_type,
            treat_mutable_obj_as_immutable=treat_mutable_obj_as_immutable,
        )

    if nested > 0 and args:
        if origin is list:
            expected_class = Sequence if treat_mutable_obj_as_immutable else list
            return isinstance(obj, expected_class) and all(
                _isinstance(
                    item,
                    args[0],
                    nested=nested - 1,
                    treat_var_as_type=treat_var_as_type,
                )
                for item in obj
            )
        if origin is tuple:
            if args[-1] is Ellipsis:
                return isinstance(obj, tuple) and all(
                    _isinstance(
                        item,
                        args[0],
                        nested=nested - 1,
                        treat_var_as_type=treat_var_as_type,
                    )
                    for item in obj
                )
            return (
                isinstance(obj, tuple)
                and len(obj) == len(args)
                and all(
                    _isinstance(
                        item,
                        arg,
                        nested=nested - 1,
                        treat_var_as_type=treat_var_as_type,
                    )
                    for item, arg in zip(obj, args, strict=True)
                )
            )
        if origin in (dict, Mapping, Breakpoints):
            expected_class = (
                dict
                if origin is dict and not treat_mutable_obj_as_immutable
                else Mapping
            )
            return isinstance(obj, expected_class) and all(
                _isinstance(
                    key, args[0], nested=nested - 1, treat_var_as_type=treat_var_as_type
                )
                and _isinstance(
                    value,
                    args[1],
                    nested=nested - 1,
                    treat_var_as_type=treat_var_as_type,
                )
                for key, value in obj.items()
            )
        if origin is set:
            expected_class = Sequence if treat_mutable_obj_as_immutable else set
            return isinstance(obj, expected_class) and all(
                _isinstance(
                    item,
                    args[0],
                    nested=nested - 1,
                    treat_var_as_type=treat_var_as_type,
                )
                for item in obj
            )

    if args:
        from reflex.vars import Field

        if origin is Field:
            return _isinstance(
                obj, args[0], nested=nested, treat_var_as_type=treat_var_as_type
            )

    return isinstance(obj, get_base_class(cls))


def is_dataframe(value: type) -> bool:
    """Check if the given value is a dataframe.

    Args:
        value: The value to check.

    Returns:
        Whether the value is a dataframe.
    """
    if is_generic_alias(value) or value == Any:
        return False
    return value.__name__ == "DataFrame"


def is_valid_var_type(type_: type) -> bool:
    """Check if the given type is a valid prop type.

    Args:
        type_: The type to check.

    Returns:
        Whether the type is a valid prop type.
    """
    from reflex.utils import serializers

    if is_union(type_):
        return all(is_valid_var_type(arg) for arg in get_args(type_))

    if is_literal(type_):
        types = {type(value) for value in get_args(type_)}
        return all(is_valid_var_type(type_) for type_ in types)

    type_ = origin if (origin := get_origin(type_)) is not None else type_

    return (
        issubclass(type_, StateVarTypes)
        or serializers.has_serializer(type_)
        or dataclasses.is_dataclass(type_)
    )


def is_backend_base_variable(name: str, cls: type) -> bool:
    """Check if this variable name correspond to a backend variable.

    Args:
        name: The name of the variable to check
        cls: The class of the variable to check

    Returns:
        bool: The result of the check
    """
    if name in RESERVED_BACKEND_VAR_NAMES:
        return False

    if not name.startswith("_"):
        return False

    if name.startswith("__"):
        return False

    if name.startswith(f"_{cls.__name__}__"):
        return False

    # Extract the namespace of the original module if defined (dynamic substates).
    if callable(getattr(cls, "_get_type_hints", None)):
        hints = cls._get_type_hints()
    else:
        hints = get_type_hints(cls)
    if name in hints:
        hint = get_origin(hints[name])
        if hint == ClassVar:
            return False

    if name in cls.inherited_backend_vars:
        return False

    from reflex.vars.base import is_computed_var

    if name in cls.__dict__:
        value = cls.__dict__[name]
        if type(value) is classmethod:
            return False
        if callable(value):
            return False

        if isinstance(
            value,
            (
                types.FunctionType,
                property,
                cached_property,
            ),
        ) or is_computed_var(value):
            return False

    return True


def check_type_in_allowed_types(value_type: type, allowed_types: Iterable) -> bool:
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

    type_ = prop._var_type if isinstance(prop, Var) else type(prop)
    return type_ in allowed_types


def is_encoded_fstring(value: Any) -> bool:
    """Check if a value is an encoded Var f-string.

    Args:
        value: The value string to check.

    Returns:
        Whether the value is an f-string
    """
    return isinstance(value, str) and constants.REFLEX_VAR_OPENING_TAG in value


def validate_literal(key: str, value: Any, expected_type: type, comp_name: str):
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
            allowed_value_str = ",".join([
                str(v) if not isinstance(v, str) else f"'{v}'" for v in allowed_values
            ])
            value_str = f"'{value}'" if isinstance(value, str) else value
            msg = f"prop value for {key!s} of the `{comp_name}` component should be one of the following: {allowed_value_str}. Got {value_str} instead"
            raise ValueError(msg)


def safe_issubclass(cls: Any, cls_check: Any | tuple[Any, ...]):
    """Check if a class is a subclass of another class. Returns False if internal error occurs.

    Args:
        cls: The class to check.
        cls_check: The class to check against.

    Returns:
        Whether the class is a subclass of the other class.
    """
    try:
        return issubclass(cls, cls_check)
    except TypeError:
        return False


def typehint_issubclass(
    possible_subclass: Any,
    possible_superclass: Any,
    *,
    treat_mutable_superclasss_as_immutable: bool = False,
    treat_literals_as_union_of_types: bool = True,
    treat_any_as_subtype_of_everything: bool = False,
) -> bool:
    """Check if a type hint is a subclass of another type hint.

    Args:
        possible_subclass: The type hint to check.
        possible_superclass: The type hint to check against.
        treat_mutable_superclasss_as_immutable: Whether to treat target classes as immutable.
        treat_literals_as_union_of_types: Whether to treat literals as a union of their types.
        treat_any_as_subtype_of_everything: Whether to treat Any as a subtype of everything. This is the default behavior in Python.

    Returns:
        Whether the type hint is a subclass of the other type hint.
    """
    if possible_subclass is possible_superclass or possible_superclass is Any:
        return True
    if possible_subclass is Any:
        return treat_any_as_subtype_of_everything
    if possible_subclass is NoReturn:
        return True

    provided_type_origin = get_origin(possible_subclass)
    accepted_type_origin = get_origin(possible_superclass)

    if provided_type_origin is None and accepted_type_origin is None:
        # In this case, we are dealing with a non-generic type, so we can use issubclass
        return issubclass(possible_subclass, possible_superclass)

    if treat_literals_as_union_of_types and is_literal(possible_superclass):
        args = get_args(possible_superclass)
        return any(
            typehint_issubclass(
                possible_subclass,
                type(arg),
                treat_mutable_superclasss_as_immutable=treat_mutable_superclasss_as_immutable,
                treat_literals_as_union_of_types=treat_literals_as_union_of_types,
                treat_any_as_subtype_of_everything=treat_any_as_subtype_of_everything,
            )
            for arg in args
        )

    if is_literal(possible_subclass):
        args = get_args(possible_subclass)
        return all(
            _isinstance(
                arg,
                possible_superclass,
                treat_mutable_obj_as_immutable=treat_mutable_superclasss_as_immutable,
                nested=2,
            )
            for arg in args
        )

    provided_type_origin = (
        Union if provided_type_origin is types.UnionType else provided_type_origin
    )
    accepted_type_origin = (
        Union if accepted_type_origin is types.UnionType else accepted_type_origin
    )

    # Get type arguments (e.g., [float, int] for dict[float, int])
    provided_args = get_args(possible_subclass)
    accepted_args = get_args(possible_superclass)

    if accepted_type_origin is Union:
        if provided_type_origin is not Union:
            return any(
                typehint_issubclass(
                    possible_subclass,
                    accepted_arg,
                    treat_mutable_superclasss_as_immutable=treat_mutable_superclasss_as_immutable,
                    treat_literals_as_union_of_types=treat_literals_as_union_of_types,
                    treat_any_as_subtype_of_everything=treat_any_as_subtype_of_everything,
                )
                for accepted_arg in accepted_args
            )
        return all(
            any(
                typehint_issubclass(
                    provided_arg,
                    accepted_arg,
                    treat_mutable_superclasss_as_immutable=treat_mutable_superclasss_as_immutable,
                    treat_literals_as_union_of_types=treat_literals_as_union_of_types,
                    treat_any_as_subtype_of_everything=treat_any_as_subtype_of_everything,
                )
                for accepted_arg in accepted_args
            )
            for provided_arg in provided_args
        )
    if provided_type_origin is Union:
        return all(
            typehint_issubclass(
                provided_arg,
                possible_superclass,
                treat_mutable_superclasss_as_immutable=treat_mutable_superclasss_as_immutable,
                treat_literals_as_union_of_types=treat_literals_as_union_of_types,
                treat_any_as_subtype_of_everything=treat_any_as_subtype_of_everything,
            )
            for provided_arg in provided_args
        )

    provided_type_origin = provided_type_origin or possible_subclass
    accepted_type_origin = accepted_type_origin or possible_superclass

    if treat_mutable_superclasss_as_immutable:
        if accepted_type_origin is dict:
            accepted_type_origin = Mapping
        elif accepted_type_origin is list or accepted_type_origin is set:
            accepted_type_origin = Sequence

    # Check if the origin of both types is the same (e.g., list for list[int])
    if not safe_issubclass(
        provided_type_origin or possible_subclass,
        accepted_type_origin or possible_superclass,
    ):
        return False

    # Ensure all specific types are compatible with accepted types
    # Note this is not necessarily correct, as it doesn't check against contravariance and covariance
    # It also ignores when the length of the arguments is different
    return all(
        typehint_issubclass(
            provided_arg,
            accepted_arg,
            treat_mutable_superclasss_as_immutable=treat_mutable_superclasss_as_immutable,
            treat_literals_as_union_of_types=treat_literals_as_union_of_types,
            treat_any_as_subtype_of_everything=treat_any_as_subtype_of_everything,
        )
        for provided_arg, accepted_arg in zip(
            provided_args, accepted_args, strict=False
        )
        if accepted_arg is not Any
    )


def resolve_annotations(
    raw_annotations: Mapping[str, type[Any]], module_name: str | None
) -> dict[str, type[Any]]:
    """Partially taken from typing.get_type_hints.

    Resolve string or ForwardRef annotations into type objects if possible.

    Args:
        raw_annotations: The raw annotations to resolve.
        module_name: The name of the module.

    Returns:
        The resolved annotations.
    """
    module = sys.modules.get(module_name, None) if module_name is not None else None

    base_globals: dict[str, Any] | None = (
        module.__dict__ if module is not None else None
    )

    annotations = {}
    for name, value in raw_annotations.items():
        if isinstance(value, str):
            if sys.version_info == (3, 10, 0):
                value = ForwardRef(value, is_argument=False)
            else:
                value = ForwardRef(value, is_argument=False, is_class=True)
        try:
            if sys.version_info >= (3, 13):
                value = _eval_type(value, base_globals, None, type_params=())
            else:
                value = _eval_type(value, base_globals, None)
        except NameError:
            # this is ok, it can be fixed with update_forward_refs
            pass
        annotations[name] = value
    return annotations


TYPES_THAT_HAS_DEFAULT_VALUE = (int, float, tuple, list, set, dict, str)


def get_default_value_for_type(t: GenericType) -> Any:
    """Get the default value of the var.

    Args:
        t: The type of the var.

    Returns:
        The default value of the var, if it has one, else None.

    Raises:
        ImportError: If the var is a dataframe and pandas is not installed.
    """
    if is_optional(t):
        return None

    origin = get_origin(t) if is_generic_alias(t) else t
    if origin is Literal:
        args = get_args(t)
        return args[0] if args else None
    if safe_issubclass(origin, TYPES_THAT_HAS_DEFAULT_VALUE):
        return origin()
    if safe_issubclass(origin, Mapping):
        return {}
    if is_dataframe(origin):
        try:
            import pandas as pd

            return pd.DataFrame()
        except ImportError as e:
            msg = "Please install pandas to use dataframes in your app."
            raise ImportError(msg) from e
    return None


IMMUTABLE_TYPES = (
    int,
    float,
    bool,
    str,
    bytes,
    frozenset,
    tuple,
    type(None),
    Enum,
)


def is_immutable(i: Any) -> bool:
    """Check if a value is immutable.

    Args:
        i: The value to check.

    Returns:
        Whether the value is immutable.
    """
    return isinstance(i, IMMUTABLE_TYPES)
