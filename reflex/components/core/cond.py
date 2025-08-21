"""Create a list of components from an iterable."""

from __future__ import annotations

from typing import Any, overload

from reflex.components.base.fragment import Fragment
from reflex.components.component import BaseComponent, Component
from reflex.components.tags import CondTag, Tag
from reflex.constants import Dirs
from reflex.style import LIGHT_COLOR_MODE, resolved_color_mode
from reflex.utils import types
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var
from reflex.vars.number import ternary_operation

_IS_TRUE_IMPORT: ImportDict = {
    f"$/{Dirs.STATE_PATH}": [ImportVar(tag="isTrue")],
}


class Cond(Component):
    """Render one of two components based on a condition."""

    # The cond to determine which component to render.
    cond: Var[Any]

    @classmethod
    def create(
        cls,
        cond: Var,
        comp1: BaseComponent,
        comp2: BaseComponent | types.Unset = types.Unset(),
    ) -> Component:
        """Create a conditional component.

        Args:
            cond: The cond to determine which component to render.
            comp1: The component to render if the cond is true.
            comp2: The component to render if the cond is false.

        Returns:
            The conditional component.
        """
        # Wrap everything in fragments.
        if type(comp1) is not Fragment:
            comp1 = Fragment.create(comp1)
        if isinstance(comp2, types.Unset) or type(comp2) is not Fragment:
            comp2 = (
                Fragment.create(comp2)
                if not isinstance(comp2, types.Unset)
                else Fragment.create()
            )
        return Fragment.create(
            cls._create(
                children=[comp1, comp2],
                cond=cond,
            )
        )

    def _render(self) -> Tag:
        return CondTag(
            cond_state=str(self.cond),
            true_value=self.children[0].render(),
            false_value=self.children[1].render(),
        )

    def render(self) -> dict:
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        return {
            "cond_state": str(self.cond),
            "true_value": self.children[0].render(),
            "false_value": self.children[1].render(),
        }

    def add_imports(self) -> ImportDict:
        """Add imports for the Cond component.

        Returns:
            The import dict for the component.
        """
        var_data = VarData.merge(self.cond._get_all_var_data())

        imports = var_data.old_school_imports() if var_data else {}

        return {**imports, **_IS_TRUE_IMPORT}


@overload
def cond(condition: Any, c1: Component, c2: Any, /) -> Component: ...  # pyright: ignore [reportOverlappingOverload]


@overload
def cond(condition: Any, c1: Component, /) -> Component: ...


@overload
def cond(condition: Any, c1: Any, c2: Component, /) -> Component: ...  # pyright: ignore [reportOverlappingOverload]


@overload
def cond(condition: Any, c1: Any, c2: Any, /) -> Var: ...


def cond(condition: Any, c1: Any, c2: Any = types.Unset(), /) -> Component | Var:
    """Create a conditional component or Prop.

    Args:
        condition: The cond to determine which component to render.
        c1: The component or prop to render if the cond_var is true.
        c2: The component or prop to render if the cond_var is false.

    Returns:
        The conditional component.

    Raises:
        ValueError: If the arguments are invalid.
    """
    # Convert the condition to a Var.
    cond_var = LiteralVar.create(condition)
    if cond_var is None:
        msg = "The condition must be set."
        raise ValueError(msg)

    # If the first component is a component, create a Cond component.
    if isinstance(c1, BaseComponent):
        if not isinstance(c2, types.Unset) and not isinstance(c2, BaseComponent):
            return Cond.create(cond_var.bool(), c1, Fragment.create(c2))
        return Cond.create(cond_var.bool(), c1, c2)

    # Otherwise, create a conditional Var.
    # Check that the second argument is valid.
    if isinstance(c2, BaseComponent):
        return Cond.create(cond_var.bool(), Fragment.create(c1), c2)
    if isinstance(c2, types.Unset):
        msg = "For conditional vars, the second argument must be set."
        raise ValueError(msg)

    # convert the truth and false cond parts into vars so the _var_data can be obtained.
    c1_var = Var.create(c1)
    c2_var = Var.create(c2)

    if c1_var is cond_var or c1_var.equals(cond_var):
        c1_var = c1_var.to(types.value_inside_optional(c1_var._var_type))

    # Create the conditional var.
    return ternary_operation(
        cond_var.bool(),
        c1_var,
        c2_var,
    )


@overload
def color_mode_cond(light: Component, dark: Component | None = None) -> Component: ...  # pyright: ignore [reportOverlappingOverload]


@overload
def color_mode_cond(light: Any, dark: Any = None) -> Var: ...


def color_mode_cond(light: Any, dark: Any = None) -> Var | Component:
    """Create a component or Prop based on color_mode.

    Args:
        light: The component or prop to render if color_mode is default
        dark: The component or prop to render if color_mode is non-default

    Returns:
        The conditional component or prop.
    """
    return cond(
        resolved_color_mode == LiteralVar.create(LIGHT_COLOR_MODE),
        light,
        dark,
    )
