"""A module for hooks-related Var."""

from __future__ import annotations

import dataclasses
import sys

from reflex.constants import Hooks

from .base import Var, VarData


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class HookVar(Var):
    """A var class for representing a hook."""

    position: Hooks.HookPosition | None = None

    @classmethod
    def create(
        cls,
        _hook_expr: str,
        _var_data: VarData | None = None,
        _position: Hooks.HookPosition | None = None,
    ):
        """Create a hook var.

        Args:
            _hook_expr: The hook expression.
            _position: The position of the hook in the component.

        Returns:
            The hook var.
        """
        hook_var = cls(
            _js_expr=_hook_expr,
            _var_type="str",
            _var_data=_var_data,
            position=_position,
        )
        # print("HookVar.create", _hook_expr, hook_var.position)
        return hook_var
