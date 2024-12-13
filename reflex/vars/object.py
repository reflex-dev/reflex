"""Classes for immutable object vars."""

from __future__ import annotations

import dataclasses
import sys
import typing
from inspect import isclass
from typing import (
    Any,
    Dict,
    List,
    NoReturn,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    overload,
)

from reflex.utils import types
from reflex.utils.exceptions import VarAttributeError
from reflex.utils.types import GenericType, get_attribute_access_type, get_origin

from .base import (
    CachedVarOperation,
    LiteralVar,
    Var,
    VarData,
    cached_property_no_lock,
    figure_out_type,
    var_operation,
    var_operation_return,
)
from .number import BooleanVar, NumberVar, raise_unsupported_operand_types
from .sequence import ArrayVar, StringVar

OBJECT_TYPE = TypeVar("OBJECT_TYPE")

KEY_TYPE = TypeVar("KEY_TYPE")
VALUE_TYPE = TypeVar("VALUE_TYPE")

ARRAY_INNER_TYPE = TypeVar("ARRAY_INNER_TYPE")

OTHER_KEY_TYPE = TypeVar("OTHER_KEY_TYPE")


class ObjectVar(Var[OBJECT_TYPE], python_types=dict):
    """Base class for immutable object vars."""

    def _key_type(self) -> Type:
        """Get the type of the keys of the object.

        Returns:
            The type of the keys of the object.
        """
        return str

    @overload
    def _value_type(
        self: ObjectVar[Dict[Any, VALUE_TYPE]],
    ) -> Type[VALUE_TYPE]: ...

    @overload
    def _value_type(self) -> Type: ...

    def _value_type(self) -> Type:
        """Get the type of the values of the object.

        Returns:
            The type of the values of the object.
        """
        fixed_type = get_origin(self._var_type) or self._var_type
        if not isclass(fixed_type):
            return Any
        args = get_args(self._var_type) if issubclass(fixed_type, dict) else ()
        return args[1] if args else Any

    def keys(self) -> ArrayVar[List[str]]:
        """Get the keys of the object.

        Returns:
            The keys of the object.
        """
        return object_keys_operation(self)

    @overload
    def values(
        self: ObjectVar[Dict[Any, VALUE_TYPE]],
    ) -> ArrayVar[List[VALUE_TYPE]]: ...

    @overload
    def values(self) -> ArrayVar: ...

    def values(self) -> ArrayVar:
        """Get the values of the object.

        Returns:
            The values of the object.
        """
        return object_values_operation(self)

    @overload
    def entries(
        self: ObjectVar[Dict[Any, VALUE_TYPE]],
    ) -> ArrayVar[List[Tuple[str, VALUE_TYPE]]]: ...

    @overload
    def entries(self) -> ArrayVar: ...

    def entries(self) -> ArrayVar:
        """Get the entries of the object.

        Returns:
            The entries of the object.
        """
        return object_entries_operation(self)

    items = entries

    def merge(self, other: ObjectVar):
        """Merge two objects.

        Args:
            other: The other object to merge.

        Returns:
            The merged object.
        """
        return object_merge_operation(self, other)

    # NoReturn is used here to catch when key value is Any
    @overload
    def __getitem__(
        self: ObjectVar[Dict[Any, NoReturn]],
        key: Var | Any,
    ) -> Var: ...

    @overload
    def __getitem__(
        self: (
            ObjectVar[Dict[Any, int]]
            | ObjectVar[Dict[Any, float]]
            | ObjectVar[Dict[Any, int | float]]
        ),
        key: Var | Any,
    ) -> NumberVar: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[Any, str]],
        key: Var | Any,
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[Any, list[ARRAY_INNER_TYPE]]],
        key: Var | Any,
    ) -> ArrayVar[list[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[Any, set[ARRAY_INNER_TYPE]]],
        key: Var | Any,
    ) -> ArrayVar[set[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[Any, tuple[ARRAY_INNER_TYPE, ...]]],
        key: Var | Any,
    ) -> ArrayVar[tuple[ARRAY_INNER_TYPE, ...]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[Any, dict[OTHER_KEY_TYPE, VALUE_TYPE]]],
        key: Var | Any,
    ) -> ObjectVar[dict[OTHER_KEY_TYPE, VALUE_TYPE]]: ...

    def __getitem__(self, key: Var | Any) -> Var:
        """Get an item from the object.

        Args:
            key: The key to get from the object.

        Returns:
            The item from the object.
        """
        if not isinstance(key, (StringVar, str, int, NumberVar)) or (
            isinstance(key, NumberVar) and key._is_strict_float()
        ):
            raise_unsupported_operand_types("[]", (type(self), type(key)))
        return ObjectItemOperation.create(self, key).guess_type()

    # NoReturn is used here to catch when key value is Any
    @overload
    def __getattr__(
        self: ObjectVar[Dict[Any, NoReturn]],
        name: str,
    ) -> Var: ...

    @overload
    def __getattr__(
        self: (
            ObjectVar[Dict[Any, int]]
            | ObjectVar[Dict[Any, float]]
            | ObjectVar[Dict[Any, int | float]]
        ),
        name: str,
    ) -> NumberVar: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[Any, str]],
        name: str,
    ) -> StringVar: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[Any, list[ARRAY_INNER_TYPE]]],
        name: str,
    ) -> ArrayVar[list[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[Any, set[ARRAY_INNER_TYPE]]],
        name: str,
    ) -> ArrayVar[set[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[Any, tuple[ARRAY_INNER_TYPE, ...]]],
        name: str,
    ) -> ArrayVar[tuple[ARRAY_INNER_TYPE, ...]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[Any, dict[OTHER_KEY_TYPE, VALUE_TYPE]]],
        name: str,
    ) -> ObjectVar[dict[OTHER_KEY_TYPE, VALUE_TYPE]]: ...

    @overload
    def __getattr__(
        self: ObjectVar,
        name: str,
    ) -> ObjectItemOperation: ...

    def __getattr__(self, name) -> Var:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Raises:
            VarAttributeError: The State var has no such attribute or may have been annotated wrongly.

        Returns:
            The attribute of the var.
        """
        if name.startswith("__") and name.endswith("__"):
            return getattr(super(type(self), self), name)

        var_type = self._var_type

        if types.is_optional(var_type):
            var_type = get_args(var_type)[0]

        fixed_type = var_type if isclass(var_type) else get_origin(var_type)
        if (isclass(fixed_type) and not issubclass(fixed_type, dict)) or (
            fixed_type in types.UnionTypes
        ):
            attribute_type = get_attribute_access_type(var_type, name)
            if attribute_type is None:
                raise VarAttributeError(
                    f"The State var `{self!s}` has no attribute '{name}' or may have been annotated "
                    f"wrongly."
                )
            return ObjectItemOperation.create(self, name, attribute_type).guess_type()
        else:
            return ObjectItemOperation.create(self, name).guess_type()

    def contains(self, key: Var | Any) -> BooleanVar:
        """Check if the object contains a key.

        Args:
            key: The key to check.

        Returns:
            The result of the check.
        """
        return object_has_own_property_operation(self, key)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralObjectVar(CachedVarOperation, ObjectVar[OBJECT_TYPE], LiteralVar):
    """Base class for immutable literal object vars."""

    _var_value: Dict[Union[Var, Any], Union[Var, Any]] = dataclasses.field(
        default_factory=dict
    )

    def _key_type(self) -> Type:
        """Get the type of the keys of the object.

        Returns:
            The type of the keys of the object.
        """
        args_list = typing.get_args(self._var_type)
        return args_list[0] if args_list else Any

    def _value_type(self) -> Type:
        """Get the type of the values of the object.

        Returns:
            The type of the values of the object.
        """
        args_list = typing.get_args(self._var_type)
        return args_list[1] if args_list else Any

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "({ "
            + ", ".join(
                [
                    f"[{LiteralVar.create(key)!s}] : {LiteralVar.create(value)!s}"
                    for key, value in self._var_value.items()
                ]
            )
            + " })"
        )

    def json(self) -> str:
        """Get the JSON representation of the object.

        Returns:
            The JSON representation of the object.
        """
        return (
            "{"
            + ", ".join(
                [
                    f"{LiteralVar.create(key).json()}:{LiteralVar.create(value).json()}"
                    for key, value in self._var_value.items()
                ]
            )
            + "}"
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((type(self).__name__, self._js_expr))

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data.

        Returns:
            The var data.
        """
        return VarData.merge(
            *[LiteralVar.create(var)._get_all_var_data() for var in self._var_value],
            *[
                LiteralVar.create(var)._get_all_var_data()
                for var in self._var_value.values()
            ],
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        _var_value: dict,
        _var_type: Type[OBJECT_TYPE] | None = None,
        _var_data: VarData | None = None,
    ) -> LiteralObjectVar[OBJECT_TYPE]:
        """Create the literal object var.

        Args:
            _var_value: The value of the var.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The literal object var.
        """
        return LiteralObjectVar(
            _js_expr="",
            _var_type=(figure_out_type(_var_value) if _var_type is None else _var_type),
            _var_data=_var_data,
            _var_value=_var_value,
        )


@var_operation
def object_keys_operation(value: ObjectVar):
    """Get the keys of an object.

    Args:
        value: The object to get the keys from.

    Returns:
        The keys of the object.
    """
    return var_operation_return(
        js_expression=f"Object.keys({value})",
        var_type=List[str],
    )


@var_operation
def object_values_operation(value: ObjectVar):
    """Get the values of an object.

    Args:
        value: The object to get the values from.

    Returns:
        The values of the object.
    """
    return var_operation_return(
        js_expression=f"Object.values({value})",
        var_type=List[value._value_type()],
    )


@var_operation
def object_entries_operation(value: ObjectVar):
    """Get the entries of an object.

    Args:
        value: The object to get the entries from.

    Returns:
        The entries of the object.
    """
    return var_operation_return(
        js_expression=f"Object.entries({value})",
        var_type=List[Tuple[str, value._value_type()]],
    )


@var_operation
def object_merge_operation(lhs: ObjectVar, rhs: ObjectVar):
    """Merge two objects.

    Args:
        lhs: The first object to merge.
        rhs: The second object to merge.

    Returns:
        The merged object.
    """
    return var_operation_return(
        js_expression=f"({{...{lhs}, ...{rhs}}})",
        var_type=Dict[
            Union[lhs._key_type(), rhs._key_type()],
            Union[lhs._value_type(), rhs._value_type()],
        ],
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ObjectItemOperation(CachedVarOperation, Var):
    """Operation to get an item from an object."""

    _object: ObjectVar = dataclasses.field(
        default_factory=lambda: LiteralObjectVar.create({})
    )
    _key: Var | Any = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        if types.is_optional(self._object._var_type):
            return f"{self._object!s}?.[{self._key!s}]"
        return f"{self._object!s}[{self._key!s}]"

    @classmethod
    def create(
        cls,
        object: ObjectVar,
        key: Var | Any,
        _var_type: GenericType | None = None,
        _var_data: VarData | None = None,
    ) -> ObjectItemOperation:
        """Create the object item operation.

        Args:
            object: The object to get the item from.
            key: The key to get from the object.
            _var_type: The type of the item.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The object item operation.
        """
        return cls(
            _js_expr="",
            _var_type=object._value_type() if _var_type is None else _var_type,
            _var_data=_var_data,
            _object=object,
            _key=key if isinstance(key, Var) else LiteralVar.create(key),
        )


@var_operation
def object_has_own_property_operation(object: ObjectVar, key: Var):
    """Check if an object has a key.

    Args:
        object: The object to check.
        key: The key to check.

    Returns:
        The result of the check.
    """
    return var_operation_return(
        js_expression=f"{object}.hasOwnProperty({key})",
        var_type=bool,
    )
