"""Classes for immutable object vars."""

from __future__ import annotations

import collections.abc
import dataclasses
import typing
from collections.abc import Mapping
from importlib.util import find_spec
from typing import (
    Any,
    NoReturn,
    TypeVar,
    get_args,
    get_type_hints,
    is_typeddict,
    overload,
)

from rich.markup import escape

from reflex.utils import types
from reflex.utils.exceptions import VarAttributeError
from reflex.utils.types import (
    GenericType,
    get_attribute_access_type,
    get_origin,
    safe_issubclass,
    unionize,
)

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
from .sequence import ArrayVar, LiteralArrayVar, StringVar

OBJECT_TYPE = TypeVar("OBJECT_TYPE", covariant=True)

KEY_TYPE = TypeVar("KEY_TYPE")
VALUE_TYPE = TypeVar("VALUE_TYPE")

ARRAY_INNER_TYPE = TypeVar("ARRAY_INNER_TYPE")

OTHER_KEY_TYPE = TypeVar("OTHER_KEY_TYPE")


def _determine_value_type(var_type: GenericType):
    origin_var_type = get_origin(var_type) or var_type

    if origin_var_type in types.UnionTypes:
        return unionize(*[
            _determine_value_type(arg)
            for arg in get_args(var_type)
            if arg is not type(None)
        ])

    if is_typeddict(origin_var_type) or dataclasses.is_dataclass(origin_var_type):
        annotations = get_type_hints(origin_var_type)
        return unionize(*annotations.values())

    if origin_var_type in [dict, Mapping, collections.abc.Mapping]:
        args = get_args(var_type)
        return args[1] if args else Any

    return Any


PYTHON_TYPES = (Mapping,)
if find_spec("pydantic"):
    import pydantic
    import pydantic.v1

    PYTHON_TYPES += (pydantic.BaseModel, pydantic.v1.BaseModel)


class ObjectVar(Var[OBJECT_TYPE], python_types=PYTHON_TYPES):
    """Base class for immutable object vars."""

    def _key_type(self) -> type:
        """Get the type of the keys of the object.

        Returns:
            The type of the keys of the object.
        """
        return str

    @overload
    def _value_type(
        self: ObjectVar[Mapping[Any, VALUE_TYPE]],
    ) -> type[VALUE_TYPE]: ...

    @overload
    def _value_type(self) -> GenericType: ...

    def _value_type(self) -> GenericType:
        """Get the type of the values of the object.

        Returns:
            The type of the values of the object.
        """
        return _determine_value_type(self._var_type)

    def keys(self) -> ArrayVar[list[str]]:
        """Get the keys of the object.

        Returns:
            The keys of the object.
        """
        return object_keys_operation(self)

    @overload
    def values(
        self: ObjectVar[Mapping[Any, VALUE_TYPE]],
    ) -> ArrayVar[list[VALUE_TYPE]]: ...

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
        self: ObjectVar[Mapping[Any, VALUE_TYPE]],
    ) -> ArrayVar[list[tuple[str, VALUE_TYPE]]]: ...

    @overload
    def entries(self) -> ArrayVar: ...

    def entries(self) -> ArrayVar:
        """Get the entries of the object.

        Returns:
            The entries of the object.
        """
        return object_entries_operation(self)

    items = entries

    def length(self) -> NumberVar[int]:
        """Get the length of the object.

        Returns:
            The length of the object.
        """
        return self.keys().length()

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
    def __getitem__(  # pyright: ignore [reportOverlappingOverload]
        self: ObjectVar[Mapping[Any, NoReturn]],
        key: Var | Any,
    ) -> Var: ...

    @overload
    def __getitem__(
        self: (ObjectVar[Mapping[Any, bool]]),
        key: Var | Any,
    ) -> BooleanVar: ...

    @overload
    def __getitem__(
        self: (
            ObjectVar[Mapping[Any, int]]
            | ObjectVar[Mapping[Any, float]]
            | ObjectVar[Mapping[Any, int | float]]
        ),
        key: Var | Any,
    ) -> NumberVar: ...

    @overload
    def __getitem__(
        self: ObjectVar[Mapping[Any, str]],
        key: Var | Any,
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ObjectVar[Mapping[Any, list[ARRAY_INNER_TYPE]]],
        key: Var | Any,
    ) -> ArrayVar[list[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Mapping[Any, tuple[ARRAY_INNER_TYPE, ...]]],
        key: Var | Any,
    ) -> ArrayVar[tuple[ARRAY_INNER_TYPE, ...]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Mapping[Any, Mapping[OTHER_KEY_TYPE, VALUE_TYPE]]],
        key: Var | Any,
    ) -> ObjectVar[Mapping[OTHER_KEY_TYPE, VALUE_TYPE]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Mapping[Any, VALUE_TYPE]],
        key: Var | Any,
    ) -> Var[VALUE_TYPE]: ...

    def __getitem__(self, key: Var | Any) -> Var:
        """Get an item from the object.

        Args:
            key: The key to get from the object.

        Returns:
            The item from the object.
        """
        from .sequence import LiteralStringVar

        if not isinstance(key, (StringVar, str, int, NumberVar)) or (
            isinstance(key, NumberVar) and key._is_strict_float()
        ):
            raise_unsupported_operand_types("[]", (type(self), type(key)))
        if isinstance(key, str) and isinstance(Var.create(key), LiteralStringVar):
            return self.__getattr__(key)
        return ObjectItemOperation.create(self, key).guess_type()

    def get(self, key: Var | Any, default: Var | Any | None = None) -> Var:
        """Get an item from the object.

        Args:
            key: The key to get from the object.
            default: The default value if the key is not found.

        Returns:
            The item from the object.
        """
        from reflex.components.core.cond import cond

        if default is None:
            default = Var.create(None)

        value = self.__getitem__(key)  # pyright: ignore[reportUnknownVariableType,reportAttributeAccessIssue,reportUnknownMemberType]

        return cond(  # pyright: ignore[reportUnknownVariableType]
            value,
            value,
            default,
        )

    # NoReturn is used here to catch when key value is Any
    @overload
    def __getattr__(  # pyright: ignore [reportOverlappingOverload]
        self: ObjectVar[Mapping[Any, NoReturn]],
        name: str,
    ) -> Var: ...

    @overload
    def __getattr__(
        self: (
            ObjectVar[Mapping[Any, int]]
            | ObjectVar[Mapping[Any, float]]
            | ObjectVar[Mapping[Any, int | float]]
        ),
        name: str,
    ) -> NumberVar: ...

    @overload
    def __getattr__(
        self: ObjectVar[Mapping[Any, str]],
        name: str,
    ) -> StringVar: ...

    @overload
    def __getattr__(
        self: ObjectVar[Mapping[Any, list[ARRAY_INNER_TYPE]]],
        name: str,
    ) -> ArrayVar[list[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Mapping[Any, tuple[ARRAY_INNER_TYPE, ...]]],
        name: str,
    ) -> ArrayVar[tuple[ARRAY_INNER_TYPE, ...]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Mapping[Any, Mapping[OTHER_KEY_TYPE, VALUE_TYPE]]],
        name: str,
    ) -> ObjectVar[Mapping[OTHER_KEY_TYPE, VALUE_TYPE]]: ...

    @overload
    def __getattr__(
        self: ObjectVar,
        name: str,
    ) -> ObjectItemOperation: ...

    def __getattr__(self, name: str) -> Var:
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

        var_type = types.value_inside_optional(var_type)

        fixed_type = get_origin(var_type) or var_type

        if (
            is_typeddict(fixed_type)
            or (
                isinstance(fixed_type, type)
                and not safe_issubclass(fixed_type, Mapping)
            )
            or (fixed_type in types.UnionTypes)
        ):
            attribute_type = get_attribute_access_type(var_type, name)
            if attribute_type is None:
                msg = (
                    f"The State var `{self!s}` of type {escape(str(self._var_type))} has no attribute '{name}' or may have been annotated "
                    f"wrongly."
                )
                raise VarAttributeError(msg)
            return ObjectItemOperation.create(self, name, attribute_type).guess_type()
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
    slots=True,
)
class LiteralObjectVar(CachedVarOperation, ObjectVar[OBJECT_TYPE], LiteralVar):
    """Base class for immutable literal object vars."""

    _var_value: Mapping[Var | Any, Var | Any] = dataclasses.field(default_factory=dict)

    def _key_type(self) -> type:
        """Get the type of the keys of the object.

        Returns:
            The type of the keys of the object.
        """
        args_list = typing.get_args(self._var_type)
        return args_list[0] if args_list else Any  # pyright: ignore [reportReturnType]

    def _value_type(self) -> type:
        """Get the type of the values of the object.

        Returns:
            The type of the values of the object.
        """
        args_list = typing.get_args(self._var_type)
        return args_list[1] if args_list else Any  # pyright: ignore [reportReturnType]

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return (
            "({ "
            + ", ".join([
                f"[{LiteralVar.create(key)!s}] : {LiteralVar.create(value)!s}"
                for key, value in self._var_value.items()
            ])
            + " })"
        )

    def json(self) -> str:
        """Get the JSON representation of the object.

        Returns:
            The JSON representation of the object.

        Raises:
            TypeError: The keys and values of the object must be literal vars to get the JSON representation
        """
        keys_and_values = []
        for key, value in self._var_value.items():
            key = LiteralVar.create(key)
            value = LiteralVar.create(value)
            if not isinstance(key, LiteralVar) or not isinstance(value, LiteralVar):
                msg = "The keys and values of the object must be literal vars to get the JSON representation."
                raise TypeError(msg)
            keys_and_values.append(f"{key.json()}:{value.json()}")
        return "{" + ", ".join(keys_and_values) + "}"

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((type(self).__name__, self._js_expr))

    @classmethod
    def _get_all_var_data_without_creating_var(
        cls,
        value: Mapping,
    ) -> VarData | None:
        """Get all the var data without creating a var.

        Args:
            value: The value to get the var data from.

        Returns:
            The var data.
        """
        return VarData.merge(
            LiteralArrayVar._get_all_var_data_without_creating_var(value),
            LiteralArrayVar._get_all_var_data_without_creating_var(value.values()),
        )

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data.

        Returns:
            The var data.
        """
        return VarData.merge(
            LiteralArrayVar._get_all_var_data_without_creating_var(self._var_value),
            LiteralArrayVar._get_all_var_data_without_creating_var(
                self._var_value.values()
            ),
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        _var_value: Mapping,
        _var_type: type[OBJECT_TYPE] | None = None,
        _var_data: VarData | None = None,
    ) -> LiteralObjectVar[OBJECT_TYPE]:
        """Create the literal object var.

        Args:
            _var_value: The value of the var.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The literal object var.

        Raises:
            TypeError: If the value is not a mapping type or a dataclass.
        """
        if not isinstance(_var_value, collections.abc.Mapping):
            from reflex.utils.serializers import serialize

            serialized = serialize(_var_value, get_type=False)
            if not isinstance(serialized, collections.abc.Mapping):
                msg = f"Expected a mapping type or a dataclass, got {_var_value!r} of type {type(_var_value).__name__}."
                raise TypeError(msg)

            return LiteralObjectVar(
                _js_expr="",
                _var_type=(type(_var_value) if _var_type is None else _var_type),
                _var_data=_var_data,
                _var_value=serialized,
            )

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
        js_expression=f"Object.keys({value} ?? {{}})",
        var_type=list[str],
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
        js_expression=f"Object.values({value} ?? {{}})",
        var_type=list[value._value_type()],
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
        js_expression=f"Object.entries({value} ?? {{}})",
        var_type=list[tuple[str, value._value_type()]],
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
        var_type=Mapping[
            lhs._key_type() | rhs._key_type(),
            lhs._value_type() | rhs._value_type(),
        ],
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
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
        return f"{self._object!s}?.[{self._key!s}]"

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
