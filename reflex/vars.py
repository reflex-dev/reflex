"""Define a state var."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    overload,  # type: ignore
)

if TYPE_CHECKING:
    from reflex.ivars import ImmutableVar, VarData


class Var:
    """An abstract var."""

    @overload
    @classmethod
    def create(
        cls,
        value: str,
        *,
        _var_is_string: bool = True,
        _var_data: Optional[VarData] = None,
        _var_is_local: bool | None = None,
    ) -> ImmutableVar: ...

    @overload
    @classmethod
    def create(
        cls,
        value: Any,
        *,
        _var_data: Optional[VarData] = None,
        _var_is_local: bool | None = None,
    ) -> ImmutableVar: ...

    @classmethod
    def create(
        cls,
        value: Any,
        *,
        _var_is_string: bool | None = None,
        _var_data: Optional[VarData] = None,
        _var_is_local: bool | None = None,
    ) -> ImmutableVar:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_is_string: Whether the var is a string literal.
            _var_data: Additional hooks and imports associated with the Var.
            _var_is_local: Whether the var is local. Deprecated.

        Returns:
            The var.
        """
        from reflex.ivars import ImmutableVar, LiteralVar

        # If the value is already a var, do nothing.
        if isinstance(value, ImmutableVar):
            return value

        # If the value is not a string, create a LiteralVar.
        if not isinstance(value, str):
            return LiteralVar.create(
                value,
                _var_data=_var_data,
            )

        # if _var_is_string is provided, use that
        if _var_is_string is False:
            return ImmutableVar.create(
                value,
                _var_data=_var_data,
            )
        if _var_is_string is True:
            return LiteralVar.create(
                value,
                _var_data=_var_data,
            )

        # TODO: Deprecate _var_is_local

        # Otherwise, rely on _var_is_local
        if _var_is_local is True:
            return LiteralVar.create(
                value,
                _var_data=_var_data,
            )
        return ImmutableVar.create(
            value,
            _var_data=_var_data,
        )

    create_safe = classmethod(create)
