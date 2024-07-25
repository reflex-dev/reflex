"""Classes for immutable object vars."""

from __future__ import annotations

import dataclasses
import sys
from functools import cached_property
from typing import Any, Dict, Type, Union

from reflex.experimental.vars.base import ImmutableVar, LiteralVar
from reflex.experimental.vars.sequence import ArrayVar
from reflex.vars import ImmutableVarData, Var, VarData


class ObjectVar(ImmutableVar):
    """Base class for immutable object vars."""

    def keys(self) -> ObjectKeysOperation:
        """Get the keys of the object.

        Returns:
            The keys of the object.
        """
        return ObjectKeysOperation(self)

    def values(self) -> ObjectValuesOperation:
        """Get the values of the object.

        Returns:
            The values of the object.
        """
        return ObjectValuesOperation(self)

    def entries(self) -> ObjectEntriesOperation:
        """Get the entries of the object.

        Returns:
            The entries of the object.
        """
        return ObjectEntriesOperation(self)

    def merge(self, other: ObjectVar) -> ObjectMergeOperation:
        """Merge two objects.

        Args:
            other: The other object to merge.

        Returns:
            The merged object.
        """
        return ObjectMergeOperation(self, other)

    def __getitem__(self, key: Var | Any) -> ObjectItemOperation:
        """Get an item from the object.

        Args:
            key: The key to get from the object.

        Returns:
            The item from the object.
        """
        return ObjectItemOperation(self, key)

    def __getattr__(self, name) -> ObjectItemOperation:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        return ObjectItemOperation(self, name)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class LiteralObjectVar(LiteralVar, ObjectVar):
    """Base class for immutable literal object vars."""

    _var_value: Dict[Union[Var, Any], Union[Var, Any]] = dataclasses.field(
        default_factory=dict
    )

    def __init__(
        self,
        _var_value: dict[Var | Any, Var | Any],
        _var_type: Type = dict,
        _var_data: VarData | None = None,
    ):
        """Initialize the object var.

        Args:
            _var_value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.
        """
        super(LiteralObjectVar, self).__init__(
            _var_name="",
            _var_type=_var_type,
            _var_data=ImmutableVarData.merge(_var_data),
        )
        object.__setattr__(
            self,
            "_var_value",
            _var_value,
        )
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
                value._get_all_var_data()
                for key, value in self._var_value
                if isinstance(value, Var)
            ],
            *[
                key._get_all_var_data()
                for key, value in self._var_value
                if isinstance(key, Var)
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
class ObjectToArrayOperation(ArrayVar):
    """Base class for object to array operations."""

    value: ObjectVar = dataclasses.field(default_factory=lambda: ObjectVar({}))

    def __init__(
        self,
        _var_value: ObjectVar,
        _var_data: VarData | None = None,
    ):
        """Initialize the object to array operation.

        Args:
            _var_value: The value of the operation.
            _var_data: Additional hooks and imports associated with the operation.
        """
        super(ObjectToArrayOperation, self).__init__(
            _var_name="",
            _var_type=_var_value._var_type,
            _var_data=_var_data,
        )
        object.__setattr__(self, "value", _var_value)
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
            self.value._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data


class ObjectKeysOperation(ObjectToArrayOperation):
    """Operation to get the keys of an object."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.keys({self.value._var_name})"


class ObjectValuesOperation(ObjectToArrayOperation):
    """Operation to get the values of an object."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.values({self.value._var_name})"


class ObjectEntriesOperation(ObjectToArrayOperation):
    """Operation to get the entries of an object."""

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.entries({self.value._var_name})"


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ObjectMergeOperation(ObjectVar):
    """Operation to merge two objects."""

    left: ObjectVar = dataclasses.field(default_factory=lambda: ObjectVar({}))
    right: ObjectVar = dataclasses.field(default_factory=lambda: ObjectVar({}))

    def __init__(
        self,
        left: ObjectVar,
        right: ObjectVar,
        _var_data: VarData | None = None,
    ):
        """Initialize the object merge operation.

        Args:
            left: The left object to merge.
            right: The right object to merge.
            _var_data: Additional hooks and imports associated with the operation.
        """
        super(ObjectMergeOperation, self).__init__(
            _var_name="",
            _var_type=left._var_type,
            _var_data=_var_data,
        )
        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"Object.assign({self.left._var_name}, {self.right._var_name})"

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
            self.left._get_all_var_data(),
            self.right._get_all_var_data(),
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
class ObjectItemOperation(ImmutableVar):
    """Operation to get an item from an object."""

    value: ObjectVar = dataclasses.field(default_factory=lambda: ObjectVar({}))
    key: Var | Any = dataclasses.field(default_factory=lambda: LiteralVar(None))

    def __init__(
        self,
        value: ObjectVar,
        key: Var | Any,
        _var_data: VarData | None = None,
    ):
        """Initialize the object item operation.

        Args:
            value: The value of the operation.
            key: The key to get from the object.
            _var_data: Additional hooks and imports associated with the operation.
        """
        super(ObjectItemOperation, self).__init__(
            _var_name="",
            _var_type=value._var_type,
            _var_data=_var_data,
        )
        object.__setattr__(self, "value", value)
        object.__setattr__(
            self, "key", key if isinstance(key, Var) else LiteralVar.create(key)
        )
        object.__delattr__(self, "_var_name")

    @cached_property
    def _cached_var_name(self) -> str:
        """The name of the operation.

        Returns:
            The name of the operation.
        """
        return f"{self.value._var_name}[{self.key._var_name}]"

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
            self.value._get_all_var_data(),
            self.key._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Wrapper method for cached property.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data
