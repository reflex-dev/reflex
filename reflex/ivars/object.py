"""Classes for immutable object vars."""

from __future__ import annotations

import dataclasses
import sys
import typing
from functools import cached_property
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

from typing_extensions import get_origin

from reflex.utils import types
from reflex.utils.exceptions import VarAttributeError
from reflex.utils.types import GenericType, get_attribute_access_type
from reflex.vars import ImmutableVarData, Var, VarData

from .base import (
    ImmutableVar,
    LiteralVar,
    figure_out_type,
)
from .number import BooleanVar, NumberVar
from .sequence import ArrayVar, StringVar

OBJECT_TYPE = TypeVar("OBJECT_TYPE", bound=Dict)

KEY_TYPE = TypeVar("KEY_TYPE")
VALUE_TYPE = TypeVar("VALUE_TYPE")

ARRAY_INNER_TYPE = TypeVar("ARRAY_INNER_TYPE")

OTHER_KEY_TYPE = TypeVar("OTHER_KEY_TYPE")


class ObjectVar(ImmutableVar[OBJECT_TYPE]):
    """Base class for immutable object vars."""

    def _key_type(self) -> Type:
        """Get the type of the keys of the object.

        Returns:
            The type of the keys of the object.
        """
        return str

    @overload
    def _value_type(self: ObjectVar[Dict[KEY_TYPE, VALUE_TYPE]]) -> VALUE_TYPE: ...

    @overload
    def _value_type(self) -> Type: ...

    def _value_type(self) -> Type:
        """Get the type of the values of the object.

        Returns:
            The type of the values of the object.
        """
        fixed_type = (
            self._var_type if isclass(self._var_type) else get_origin(self._var_type)
        )
        if not isclass(fixed_type):
            return Any
        args = get_args(self._var_type) if issubclass(fixed_type, dict) else ()
        return args[1] if args else Any

    def keys(self) -> ArrayVar[List[str]]:
        """Get the keys of the object.

        Returns:
            The keys of the object.
        """
        return ObjectKeysOperation.create(self)

    @overload
    def values(
        self: ObjectVar[Dict[KEY_TYPE, VALUE_TYPE]],
    ) -> ArrayVar[List[VALUE_TYPE]]: ...

    @overload
    def values(self) -> ArrayVar: ...

    def values(self) -> ArrayVar:
        """Get the values of the object.

        Returns:
            The values of the object.
        """
        return ObjectValuesOperation.create(self)

    @overload
    def entries(
        self: ObjectVar[Dict[KEY_TYPE, VALUE_TYPE]],
    ) -> ArrayVar[List[Tuple[str, VALUE_TYPE]]]: ...

    @overload
    def entries(self) -> ArrayVar: ...

    def entries(self) -> ArrayVar:
        """Get the entries of the object.

        Returns:
            The entries of the object.
        """
        return ObjectEntriesOperation.create(self)

    def merge(self, other: ObjectVar) -> ObjectMergeOperation:
        """Merge two objects.

        Args:
            other: The other object to merge.

        Returns:
            The merged object.
        """
        return ObjectMergeOperation.create(self, other)

    # NoReturn is used here to catch when key value is Any
    @overload
    def __getitem__(
        self: ObjectVar[Dict[KEY_TYPE, NoReturn]],
        key: Var | Any,
    ) -> ImmutableVar: ...

    @overload
    def __getitem__(
        self: (
            ObjectVar[Dict[KEY_TYPE, int]]
            | ObjectVar[Dict[KEY_TYPE, float]]
            | ObjectVar[Dict[KEY_TYPE, int | float]]
        ),
        key: Var | Any,
    ) -> NumberVar: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[KEY_TYPE, str]],
        key: Var | Any,
    ) -> StringVar: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[KEY_TYPE, list[ARRAY_INNER_TYPE]]],
        key: Var | Any,
    ) -> ArrayVar[list[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[KEY_TYPE, set[ARRAY_INNER_TYPE]]],
        key: Var | Any,
    ) -> ArrayVar[set[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[KEY_TYPE, tuple[ARRAY_INNER_TYPE, ...]]],
        key: Var | Any,
    ) -> ArrayVar[tuple[ARRAY_INNER_TYPE, ...]]: ...

    @overload
    def __getitem__(
        self: ObjectVar[Dict[KEY_TYPE, dict[OTHER_KEY_TYPE, VALUE_TYPE]]],
        key: Var | Any,
    ) -> ObjectVar[dict[OTHER_KEY_TYPE, VALUE_TYPE]]: ...

    def __getitem__(self, key: Var | Any) -> ImmutableVar:
        """Get an item from the object.

        Args:
            key: The key to get from the object.

        Returns:
            The item from the object.
        """
        return ObjectItemOperation.create(self, key).guess_type()

    # NoReturn is used here to catch when key value is Any
    @overload
    def __getattr__(
        self: ObjectVar[Dict[KEY_TYPE, NoReturn]],
        name: str,
    ) -> ImmutableVar: ...

    @overload
    def __getattr__(
        self: (
            ObjectVar[Dict[KEY_TYPE, int]]
            | ObjectVar[Dict[KEY_TYPE, float]]
            | ObjectVar[Dict[KEY_TYPE, int | float]]
        ),
        name: str,
    ) -> NumberVar: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[KEY_TYPE, str]],
        name: str,
    ) -> StringVar: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[KEY_TYPE, list[ARRAY_INNER_TYPE]]],
        name: str,
    ) -> ArrayVar[list[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[KEY_TYPE, set[ARRAY_INNER_TYPE]]],
        name: str,
    ) -> ArrayVar[set[ARRAY_INNER_TYPE]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[KEY_TYPE, tuple[ARRAY_INNER_TYPE, ...]]],
        name: str,
    ) -> ArrayVar[tuple[ARRAY_INNER_TYPE, ...]]: ...

    @overload
    def __getattr__(
        self: ObjectVar[Dict[KEY_TYPE, dict[OTHER_KEY_TYPE, VALUE_TYPE]]],
        name: str,
    ) -> ObjectVar[dict[OTHER_KEY_TYPE, VALUE_TYPE]]: ...

    def __getattr__(self, name) -> ImmutableVar:
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
        if isclass(fixed_type) and not issubclass(fixed_type, dict):
            attribute_type = get_attribute_access_type(var_type, name)
            if attribute_type is None:
                raise VarAttributeError(
                    f"The State var `{self._var_name}` has no attribute '{name}' or may have been annotated "
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
        return ObjectHasOwnProperty.create(self, key)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralObjectVar(LiteralVar, ObjectVar[OBJECT_TYPE]):
    """Base class for immutable literal object vars."""

    _var_value: Dict[Union[Var, Any], Union[Var, Any]] = dataclasses.field(
        default_factory=dict
    )

    def __post_init__(self):
        """Post initialization."""
        object.__delattr__(self, "_var_name")

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
            "({ "
            + ", ".join(
                [
                    f"[{str(LiteralVar.create(key))}] : {str(LiteralVar.create(value))}"
                    for key, value in self._var_value.items()
                ]
            )
            + " })"
        )

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            *[
                LiteralVar.create(value)._get_all_var_data()
                for value in self._var_value.values()
            ],
            *[LiteralVar.create(key)._get_all_var_data() for key in self._var_value],
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

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
        return hash((self.__class__.__name__, self._var_name))

    @classmethod
    def create(
        cls,
        _var_value: OBJECT_TYPE,
        _var_type: GenericType | None = None,
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
            _var_name="",
            _var_type=(figure_out_type(_var_value) if _var_type is None else _var_type),
            _var_data=ImmutableVarData.merge(_var_data),
            _var_value=_var_value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ObjectToArrayOperation(ArrayVar):
    """Base class for object to array operations."""

    _value: ObjectVar = dataclasses.field(
        default_factory=lambda: LiteralObjectVar.create({})
    )

    def __post_init__(self):
        """Post initialization."""
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Raises:
            NotImplementedError: Must implement _cached_var_name.
        """
        raise NotImplementedError(
            "ObjectToArrayOperation must implement _cached_var_name"
        )

    def __getattr__(self, name):
        """Get an attribute of the operation.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the operation.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the operation.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._value._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __hash__(self) -> int:
        """Get the hash of the operation.

        Returns:
            The hash of the operation.
        """
        return hash((self.__class__.__name__, self._value))

    @classmethod
    def create(
        cls,
        value: ObjectVar,
        _var_type: GenericType | None = None,
        _var_data: VarData | None = None,
    ) -> ObjectToArrayOperation:
        """Create the object to array operation.

        Args:
            value: The value of the operation.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The object to array operation.
        """
        return cls(
            _var_name="",
            _var_type=list if _var_type is None else _var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


class ObjectKeysOperation(ObjectToArrayOperation):
    """Operation to get the keys of an object."""

    #         value, List[value._key_type()], _var_data
    #     )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.keys({str(self._value)})"

    @classmethod
    def create(
        cls,
        value: ObjectVar,
        _var_data: VarData | None = None,
    ) -> ObjectKeysOperation:
        """Create the object keys operation.

        Args:
            value: The value of the operation.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The object keys operation.
        """
        return cls(
            _var_name="",
            _var_type=List[str],
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


class ObjectValuesOperation(ObjectToArrayOperation):
    """Operation to get the values of an object."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.values({self._value._var_name})"

    @classmethod
    def create(
        cls,
        value: ObjectVar,
        _var_data: VarData | None = None,
    ) -> ObjectValuesOperation:
        """Create the object values operation.

        Args:
            value: The value of the operation.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The object values operation.
        """
        return cls(
            _var_name="",
            _var_type=List[value._value_type()],
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


class ObjectEntriesOperation(ObjectToArrayOperation):
    """Operation to get the entries of an object."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.entries({self._value._var_name})"

    @classmethod
    def create(
        cls,
        value: ObjectVar,
        _var_data: VarData | None = None,
    ) -> ObjectEntriesOperation:
        """Create the object entries operation.

        Args:
            value: The value of the operation.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The object entries operation.
        """
        return cls(
            _var_name="",
            _var_type=List[Tuple[str, value._value_type()]],
            _var_data=ImmutableVarData.merge(_var_data),
            _value=value,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ObjectMergeOperation(ObjectVar):
    """Operation to merge two objects."""

    _lhs: ObjectVar = dataclasses.field(
        default_factory=lambda: LiteralObjectVar.create({})
    )
    _rhs: ObjectVar = dataclasses.field(
        default_factory=lambda: LiteralObjectVar.create({})
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.assign({self._lhs._var_name}, {self._rhs._var_name})"

    def __getattr__(self, name):
        """Get an attribute of the operation.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the operation.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the operation.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._lhs._get_all_var_data(),
            self._rhs._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __hash__(self) -> int:
        """Get the hash of the operation.

        Returns:
            The hash of the operation.
        """
        return hash((self.__class__.__name__, self._lhs, self._rhs))

    def __post_init__(self):
        """Post initialization."""
        object.__delattr__(self, "_var_name")

    @classmethod
    def create(
        cls,
        lhs: ObjectVar,
        rhs: ObjectVar,
        _var_data: VarData | None = None,
    ) -> ObjectMergeOperation:
        """Create the object merge operation.

        Args:
            lhs: The left object to merge.
            rhs: The right object to merge.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The object merge operation.
        """
        # TODO: Figure out how to merge the types
        return cls(
            _var_name="",
            _var_type=lhs._var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _lhs=lhs,
            _rhs=rhs,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ObjectItemOperation(ImmutableVar):
    """Operation to get an item from an object."""

    _object: ObjectVar = dataclasses.field(
        default_factory=lambda: LiteralObjectVar.create({})
    )
    _key: Var | Any = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        if types.is_optional(self._object._var_type):
            return f"{str(self._object)}?.[{str(self._key)}]"
        return f"{str(self._object)}[{str(self._key)}]"

    def __getattr__(self, name):
        """Get an attribute of the operation.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the operation.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the operation.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._object._get_all_var_data(),
            self._key._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __hash__(self) -> int:
        """Get the hash of the operation.

        Returns:
            The hash of the operation.
        """
        return hash((self.__class__.__name__, self._object, self._key))

    def __post_init__(self):
        """Post initialization."""
        object.__delattr__(self, "_var_name")

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
            _var_name="",
            _var_type=object._value_type() if _var_type is None else _var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _object=object,
            _key=key if isinstance(key, Var) else LiteralVar.create(key),
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ToObjectOperation(ObjectVar):
    """Operation to convert a var to an object."""

    _original_var: Var = dataclasses.field(
        default_factory=lambda: LiteralObjectVar.create({})
    )

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return str(self._original_var)

    def __getattr__(self, name):
        """Get an attribute of the operation.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the operation.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the operation.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._original_var._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __hash__(self) -> int:
        """Get the hash of the operation.

        Returns:
            The hash of the operation.
        """
        return hash((self.__class__.__name__, self._original_var))

    def __post_init__(self):
        """Post initialization."""
        object.__delattr__(self, "_var_name")

    @classmethod
    def create(
        cls,
        original_var: Var,
        _var_type: GenericType | None = None,
        _var_data: VarData | None = None,
    ) -> ToObjectOperation:
        """Create the to object operation.

        Args:
            original_var: The original var to convert.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The to object operation.
        """
        return cls(
            _var_name="",
            _var_type=dict if _var_type is None else _var_type,
            _var_data=ImmutableVarData.merge(_var_data),
            _original_var=original_var,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ObjectHasOwnProperty(BooleanVar):
    """Operation to check if an object has a property."""

    _object: ObjectVar = dataclasses.field(
        default_factory=lambda: LiteralObjectVar.create({})
    )
    _key: Var | Any = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    def __post_init__(self):
        """Post initialization."""
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"{str(self._object)}.hasOwnProperty({str(self._key)})"

    def __getattr__(self, name):
        """Get an attribute of the operation.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the operation.
        """
        if name == "_var_name":
            return self._cached_var_name
        return super(type(self), self).__getattr__(name)

    @cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the operation.

        Returns:
            The VarData of the components and all of its children.
        """
        return ImmutableVarData.merge(
            self._object._get_all_var_data(),
            self._key._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __hash__(self) -> int:
        """Get the hash of the operation.

        Returns:
            The hash of the operation.
        """
        return hash((self.__class__.__name__, self._object, self._key))

    @classmethod
    def create(
        cls,
        object: ObjectVar,
        key: Var | Any,
        _var_data: VarData | None = None,
    ) -> ObjectHasOwnProperty:
        """Create the object has own property operation.

        Args:
            object: The object to check.
            key: The key to check.
            _var_data: Additional hooks and imports associated with the operation.

        Returns:
            The object has own property operation.
        """
        return cls(
            _var_name="",
            _var_type=bool,
            _var_data=ImmutableVarData.merge(_var_data),
            _object=object,
            _key=key if isinstance(key, Var) else LiteralVar.create(key),
        )
