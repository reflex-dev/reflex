"""Collection of base classes."""

import dataclasses
import sys
from typing import Any, Literal, Optional, Self, Type, Union, get_args, get_origin

from reflex.utils import types
from reflex.vars import Var, VarData


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
