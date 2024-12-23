"""Create a list of components from an iterable."""

from __future__ import annotations

from typing import Any, Dict, Optional, overload

from reflex.components.base.fragment import Fragment
from reflex.components.component import BaseComponent, Component, MemoizationLeaf
from reflex.components.tags import CondTag, Tag
from reflex.constants import Dirs
from reflex.style import LIGHT_COLOR_MODE, resolved_color_mode
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var
from reflex.vars.number import ternary_operation

_IS_TRUE_IMPORT: ImportDict = {
    f"$/{Dirs.STATE_PATH}": [ImportVar(tag="isTrue")],
}


class Cond(MemoizationLeaf):
    """Render one of two components based on a condition."""

    # The cond to determine which component to render.
    cond: Var[Any]

    # The component to render if the cond is true.
    comp1: BaseComponent = None  # type: ignore

    # The component to render if the cond is false.
    comp2: BaseComponent = None  # type: ignore

    @classmethod
    def create(
        cls,
        cond: Var,
        comp1: BaseComponent,
        comp2: Optional[BaseComponent] = None,
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
        if type(comp1).__name__ != "Fragment":
            comp1 = Fragment.create(comp1)
        if comp2 is None or type(comp2).__name__ != "Fragment":
            comp2 = Fragment.create(comp2) if comp2 else Fragment.create()
        return Fragment.create(
            cls(
                cond=cond,
                comp1=comp1,
                comp2=comp2,
                children=[comp1, comp2],
            )
        )

    def _get_props_imports(self):
        """Get the imports needed for component's props.

        Returns:
            The imports for the component's props of the component.
        """
        return []

    def _render(self) -> Tag:
        return CondTag(
            cond=self.cond,
            true_value=self.comp1.render(),
            false_value=self.comp2.render(),
        )

    def render(self) -> Dict:
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()
        return dict(
            tag.add_props(
                **self.event_triggers,
                key=self.key,
                sx=self.style,
                id=self.id,
                class_name=self.class_name,
            ).set(
                props=tag.format_props(),
            ),
            cond_state=f"isTrue({self.cond!s})",
        )

    def add_imports(self) -> ImportDict:
        """Add imports for the Cond component.

        Returns:
            The import dict for the component.
        """
        var_data = VarData.merge(self.cond._get_all_var_data())

        imports = var_data.old_school_imports() if var_data else {}

        return {**imports, **_IS_TRUE_IMPORT}


@overload
def cond(condition: Any, c1: Component, c2: Any) -> Component: ...


@overload
def cond(condition: Any, c1: Component) -> Component: ...


@overload
def cond(condition: Any, c1: Any, c2: Any) -> Var: ...


def cond(condition: Any, c1: Any, c2: Any = None) -> Component | Var:
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
        raise ValueError("The condition must be set.")

    # If the first component is a component, create a Cond component.
    if isinstance(c1, BaseComponent):
        if c2 is not None and not isinstance(c2, BaseComponent):
            raise ValueError("Both arguments must be components.")
        return Cond.create(cond_var, c1, c2)

    # Otherwise, create a conditional Var.
    # Check that the second argument is valid.
    if isinstance(c2, BaseComponent):
        raise ValueError("Both arguments must be props.")
    if c2 is None:
        raise ValueError("For conditional vars, the second argument must be set.")

    def create_var(cond_part):
        return LiteralVar.create(cond_part)

    # convert the truth and false cond parts into vars so the _var_data can be obtained.
    c1 = create_var(c1)
    c2 = create_var(c2)

    # Create the conditional var.
    return ternary_operation(
        cond_var.bool()._replace(  # type: ignore
            merge_var_data=VarData(imports=_IS_TRUE_IMPORT),
        ),  # type: ignore
        c1,
        c2,
    )


@overload
def color_mode_cond(light: Component, dark: Component | None = None) -> Component: ...  # type: ignore


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
