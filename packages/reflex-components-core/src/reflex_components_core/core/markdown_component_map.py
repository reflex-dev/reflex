"""Markdown component map mixin."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import ClassVar

from reflex_base.vars.base import Var, VarData
from reflex_base.vars.function import ArgsFunctionOperation, DestructuredArg

# Special vars used in the component map.
_CHILDREN = Var(_js_expr="children", _var_type=str)
_PROPS_SPREAD = Var(_js_expr="...props")


@dataclasses.dataclass()
class MarkdownComponentMap:
    """Mixin class for handling custom component maps in Markdown components."""

    _explicit_return: ClassVar[bool] = False

    @classmethod
    def get_component_map_custom_code(cls) -> Var:
        """Get the custom code for the component map.

        Returns:
            The custom code for the component map.
        """
        return Var("")

    @classmethod
    def create_map_fn_var(
        cls,
        fn_body: Var | None = None,
        fn_args: Sequence[str] | None = None,
        explicit_return: bool | None = None,
        var_data: VarData | None = None,
    ) -> Var:
        """Create a function Var for the component map.

        Args:
            fn_body: The formatted component as a string.
            fn_args: The function arguments.
            explicit_return: Whether to use explicit return syntax.
            var_data: The var data for the function.

        Returns:
            The function Var for the component map.
        """
        fn_args = fn_args or cls.get_fn_args()
        fn_body = fn_body if fn_body is not None else cls.get_fn_body()
        explicit_return = explicit_return or cls._explicit_return

        return ArgsFunctionOperation.create(
            args_names=(DestructuredArg(fields=tuple(fn_args)),),
            return_expr=fn_body,
            explicit_return=explicit_return,
            _var_data=var_data,
        )

    @classmethod
    def get_fn_args(cls) -> Sequence[str]:
        """Get the function arguments for the component map.

        Returns:
            The function arguments as a list of strings.
        """
        return ["node", _CHILDREN._js_expr, _PROPS_SPREAD._js_expr]

    @classmethod
    def get_fn_body(cls) -> Var:
        """Get the function body for the component map.

        Returns:
            The function body as a string.
        """
        return Var(_js_expr="undefined", _var_type=None)
