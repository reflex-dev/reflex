"""Vars for colors."""

import dataclasses

from reflex.constants.colors import Color
from reflex.vars.base import (
    CachedVarOperation,
    LiteralVar,
    Var,
    VarData,
    cached_property_no_lock,
    get_python_literal,
)
from reflex.vars.number import ternary_operation
from reflex.vars.sequence import ConcatVarOperation, LiteralStringVar, StringVar


class ColorVar(StringVar[Color], python_types=Color):
    """Base class for immutable color vars."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralColorVar(CachedVarOperation, LiteralVar, ColorVar):
    """Base class for immutable literal color vars."""

    _var_value: Color = dataclasses.field(default_factory=lambda: Color(color="black"))

    @classmethod
    def _get_all_var_data_without_creating_var(
        cls,
        value: Color,
    ) -> VarData | None:
        return VarData.merge(
            LiteralStringVar._get_all_var_data_without_creating_var(value.color)
            if isinstance(value.color, str)
            else value.color._get_all_var_data(),
            value.alpha._get_all_var_data()
            if not isinstance(value.alpha, bool)
            else None,
            value.shade._get_all_var_data()
            if not isinstance(value.shade, int)
            else None,
        )

    @classmethod
    def create(
        cls,
        value: Color,
        _var_type: type[Color] | None = None,
        _var_data: VarData | None = None,
    ) -> ColorVar:
        """Create a var from a string value.

        Args:
            value: The value to create the var from.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return cls(
            _js_expr="",
            _var_type=_var_type or Color,
            _var_data=_var_data,
            _var_value=value,
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((
            self.__class__.__name__,
            self._var_value.color,
            self._var_value.alpha,
            self._var_value.shade,
        ))

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        alpha = self._var_value.alpha
        alpha = (
            ternary_operation(
                alpha,
                LiteralStringVar.create("a"),
                LiteralStringVar.create(""),
            )
            if isinstance(alpha, Var)
            else LiteralStringVar.create("a" if alpha else "")
        )

        shade = self._var_value.shade
        shade = (
            shade.to_string(use_json=False)
            if isinstance(shade, Var)
            else LiteralStringVar.create(str(shade))
        )
        return str(
            ConcatVarOperation.create(
                LiteralStringVar.create("var(--"),
                self._var_value.color,
                LiteralStringVar.create("-"),
                alpha,
                shade,
                LiteralStringVar.create(")"),
            )
        )

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data.

        Returns:
            The var data.
        """
        return VarData.merge(
            LiteralStringVar._get_all_var_data_without_creating_var(
                self._var_value.color
            )
            if isinstance(self._var_value.color, str)
            else self._var_value.color._get_all_var_data(),
            self._var_value.alpha._get_all_var_data()
            if not isinstance(self._var_value.alpha, bool)
            else None,
            self._var_value.shade._get_all_var_data()
            if not isinstance(self._var_value.shade, int)
            else None,
            self._var_data,
        )

    def json(self) -> str:
        """Get the JSON representation of the var.

        Returns:
            The JSON representation of the var.

        Raises:
            TypeError: If the color is not a valid color.
        """
        color, alpha, shade = map(
            get_python_literal,
            (self._var_value.color, self._var_value.alpha, self._var_value.shade),
        )
        if color is None or alpha is None or shade is None:
            msg = "Cannot serialize color that contains non-literal vars."
            raise TypeError(msg)
        if (
            not isinstance(color, str)
            or not isinstance(alpha, bool)
            or not isinstance(shade, int)
        ):
            msg = "Color is not a valid color."
            raise TypeError(msg)
        return f"var(--{color}-{'a' if alpha else ''}{shade})"
