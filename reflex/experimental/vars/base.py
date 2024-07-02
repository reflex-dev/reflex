"""Collection of base classes."""

import dataclasses
import sys
from typing import Any, Literal, Optional, Type, Union, get_args, get_origin

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

    def get_default_value(self) -> Any:
        """Get the default value of the var.

        Returns:
            The default value of the var.

        Raises:
            ImportError: If the var is a dataframe and pandas is not installed.
        """
        if types.is_optional(self._var_type):
            return None

        type_ = (
            get_origin(self._var_type)
            if types.is_generic_alias(self._var_type)
            else self._var_type
        )
        if type_ is Literal:
            args = get_args(self._var_type)
            return args[0] if args else None
        if issubclass(type_, str):
            return ""
        if issubclass(type_, types.get_args(Union[int, float])):
            return 0
        if issubclass(type_, bool):
            return False
        if issubclass(type_, list):
            return []
        if issubclass(type_, dict):
            return {}
        if issubclass(type_, tuple):
            return ()
        if types.is_dataframe(type_):
            try:
                import pandas as pd

                return pd.DataFrame()
            except ImportError as e:
                raise ImportError(
                    "Please install pandas to use dataframes in your app."
                ) from e
        return set() if issubclass(type_, set) else None
