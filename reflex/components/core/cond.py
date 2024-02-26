"""Create a list of components from an iterable."""
from __future__ import annotations

from typing import Any, Dict, Optional, overload

from reflex.components.base.fragment import Fragment
from reflex.components.component import BaseComponent, Component, MemoizationLeaf
from reflex.components.tags import CondTag, Tag
from reflex.constants import Dirs
from reflex.constants.colors import Color
from reflex.style import LIGHT_COLOR_MODE, color_mode
from reflex.utils import format, imports
from reflex.vars import BaseVar, Var, VarData

_IS_TRUE_IMPORT = {
    f"/{Dirs.STATE_PATH}": {imports.ImportVar(tag="isTrue")},
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
        if comp1.__class__.__name__ != "Fragment":
            comp1 = Fragment.create(comp1)
        if comp2 is None or comp2.__class__.__name__ != "Fragment":
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
            cond_state=f"isTrue({self.cond._var_full_name})",
        )

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            getattr(self.cond._var_data, "imports", {}),
            _IS_TRUE_IMPORT,
        )

    def _apply_theme(self, theme: Component):
        """Apply the theme to this component.

        Args:
            theme: The theme to apply.
        """
        self.comp1.apply_theme(theme)  # type: ignore
        self.comp2.apply_theme(theme)  # type: ignore


@overload
def cond(condition: Any, c1: Component, c2: Any) -> Component:
    ...


@overload
def cond(condition: Any, c1: Component) -> Component:
    ...


@overload
def cond(condition: Any, c1: Any, c2: Any) -> Var:
    ...


def cond(condition: Any, c1: Any, c2: Any = None):
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
    var_datas: list[VarData | None] = [
        VarData(  # type: ignore
            imports=_IS_TRUE_IMPORT,
        ),
    ]

    # Convert the condition to a Var.
    cond_var = Var.create(condition)
    assert cond_var is not None, "The condition must be set."

    # If the first component is a component, create a Cond component.
    if isinstance(c1, BaseComponent):
        assert c2 is None or isinstance(
            c2, BaseComponent
        ), "Both arguments must be components."
        return Cond.create(cond_var, c1, c2)
    if isinstance(c1, Var):
        var_datas.append(c1._var_data)

    # Otherwise, create a conditional Var.
    # Check that the second argument is valid.
    if isinstance(c2, BaseComponent):
        raise ValueError("Both arguments must be props.")
    if c2 is None:
        raise ValueError("For conditional vars, the second argument must be set.")
    if isinstance(c2, Var):
        var_datas.append(c2._var_data)

    def create_var(cond_part):
        return Var.create_safe(
            cond_part,
            _var_is_string=type(cond_part) is str or isinstance(cond_part, Color),
        )

    # convert the truth and false cond parts into vars so the _var_data can be obtained.
    c1 = create_var(c1)
    c2 = create_var(c2)
    var_datas.extend([c1._var_data, c2._var_data])

    # Create the conditional var.
    return cond_var._replace(
        _var_name=format.format_cond(
            cond=cond_var._var_full_name,
            true_value=c1,
            false_value=c2,
            is_prop=True,
        ),
        _var_type=c1._var_type if isinstance(c1, BaseVar) else type(c1),
        _var_is_local=False,
        _var_full_name_needs_state_prefix=False,
        merge_var_data=VarData.merge(*var_datas),
    )


def color_mode_cond(light: Any, dark: Any = None) -> Var | Component:
    """Create a component or Prop based on color_mode.

    Args:
        light: The component or prop to render if color_mode is default
        dark: The component or prop to render if color_mode is non-default

    Returns:
        The conditional component or prop.
    """
    return cond(
        color_mode == LIGHT_COLOR_MODE,
        light,
        dark,
    )
