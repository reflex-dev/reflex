"""Create a list of components from an iterable."""
from __future__ import annotations

from typing import Any, Dict, Optional

from reflex.components.component import Component
from reflex.components.layout.fragment import Fragment
from reflex.components.tags import CondTag, Tag
from reflex.utils import format
from reflex.vars import Var


class Cond(Component):
    """Render one of two components based on a condition."""

    # The cond to determine which component to render.
    cond: Var[Any]

    # The component to render if the cond is true.
    comp1: Component = Fragment.create()

    # The component to render if the cond is false.
    comp2: Component = Fragment.create()

    @classmethod
    def create(
        cls,
        cond: Var,
        comp1: Component,
        comp2: Optional[Component] = None,
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
            cond_state=f"isTrue({self.cond.full_name})",
        )


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
    # Import here to avoid circular imports.
    from reflex.vars import BaseVar, Var

    # Convert the condition to a Var.
    cond_var = Var.create(condition)
    assert cond_var is not None, "The condition must be set."

    # If the first component is a component, create a Cond component.
    if isinstance(c1, Component):
        assert c2 is None or isinstance(
            c2, Component
        ), "Both arguments must be components."
        return Cond.create(cond_var, c1, c2)

    # Otherwise, create a conditionl Var.
    # Check that the second argument is valid.
    if isinstance(c2, Component):
        raise ValueError("Both arguments must be props.")
    if c2 is None:
        raise ValueError("For conditional vars, the second argument must be set.")

    # Create the conditional var.
    return BaseVar(
        name=format.format_cond(
            cond=cond_var.full_name,
            true_value=c1,
            false_value=c2,
            is_prop=True,
        ),
        type_=c1.type_ if isinstance(c1, BaseVar) else type(c1),
    )
