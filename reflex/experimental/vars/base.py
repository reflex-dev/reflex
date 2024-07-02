"""Collection of base classes."""

import dataclasses
import sys
from typing import Any, Optional, Self, Type

from reflex.utils import console, serializers, types
from reflex.utils.exceptions import VarTypeError
from reflex.vars import Var, VarData, _extract_var_data


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ImmutableVar(Var):
    """Base class for immutable vars."""

    # The name of the var.
    _var_name: str = dataclasses.field()

    # The type of the var.
    _var_type: Type = dataclasses.field(default=Any)

    # Whether this is a local javascript variable.
    _var_is_local: bool = dataclasses.field(default=False)

    # Whether the var is a string literal.
    _var_is_string: bool = dataclasses.field(default=False)

    # _var_full_name should be prefixed with _var_state
    _var_full_name_needs_state_prefix: bool = dataclasses.field(default=False)

    # Extra metadata associated with the Var
    _var_data: Optional[VarData] = dataclasses.field(default=None)

    def _replace(self, merge_var_data=None, **kwargs: Any) -> Self:
        """Make a copy of this Var with updated fields.

        Args:
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            A new ImmutableVar with the updated fields overwriting the corresponding fields in this Var.
        """
        field_values = dict(
            _var_name=kwargs.pop("_var_name", self._var_name),
            _var_type=kwargs.pop("_var_type", self._var_type),
            _var_is_local=kwargs.pop("_var_is_local", self._var_is_local),
            _var_is_string=kwargs.pop("_var_is_string", self._var_is_string),
            _var_full_name_needs_state_prefix=kwargs.pop(
                "_var_full_name_needs_state_prefix",
                self._var_full_name_needs_state_prefix,
            ),
            _var_data=VarData.merge(
                kwargs.get("_var_data", self._var_data), merge_var_data
            ),
        )
        return ImmutableVar(**field_values)

    @classmethod
    def create(
        cls,
        value: Any,
        _var_is_local: bool = True,
        _var_is_string: bool | None = None,
        _var_data: Optional[VarData] = None,
    ) -> Var | None:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local.
            _var_is_string: Whether the var is a string literal.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.

        Raises:
            VarTypeError: If the value is JSON-unserializable.
        """
        from reflex.utils import format

        # Check for none values.
        if value is None:
            return None

        # If the value is already a var, do nothing.
        if isinstance(value, Var):
            return value

        # Try to pull the imports and hooks from contained values.
        if not isinstance(value, str):
            _var_data = VarData.merge(*_extract_var_data(value), _var_data)

        # Try to serialize the value.
        type_ = type(value)
        if type_ in types.JSONType:
            name = value
        else:
            name, serialized_type = serializers.serialize(value, get_type=True)
            if (
                serialized_type is not None
                and _var_is_string is None
                and issubclass(serialized_type, str)
            ):
                _var_is_string = True
        if name is None:
            raise VarTypeError(
                f"No JSON serializer found for var {value} of type {type_}."
            )
        name = name if isinstance(name, str) else format.json_dumps(name)

        if _var_is_string is None and type_ is str:
            console.deprecate(
                feature_name=f"Creating a Var ({value}) from a string without specifying _var_is_string",
                reason=(
                    "Specify _var_is_string=False to create a Var that is not a string literal. "
                    "In the future, creating a Var from a string will be treated as a string literal "
                    "by default."
                ),
                deprecation_version="0.5.4",
                removal_version="0.6.0",
            )

        return ImmutableVar(
            _var_name=name,
            _var_type=type_,
            _var_is_local=_var_is_local,
            _var_is_string=_var_is_string if _var_is_string is not None else False,
            _var_data=_var_data,
        )
