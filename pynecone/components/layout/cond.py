"""Create a list of components from an iterable."""
from __future__ import annotations

from typing import Any, Optional

from pynecone.components.component import Component
from pynecone.components.layout.fragment import Fragment
from pynecone.components.tags import CondTag, Tag
from pynecone.var import Var


class Cond(Component):
    """Render one of two components based on a condition."""

    # The cond to determine which component to render.
    cond: Var[Any]

    # The component to render if the cond is true.
    comp1: Component

    # The component to render if the cond is false.
    comp2: Component

    # Whether the cond is within another cond.
    is_nested: bool = False

    @classmethod
    def create(
        cls, cond: Var, comp1: Component, comp2: Optional[Component] = None
    ) -> Cond:
        """Create a conditional component.

        Args:
            cond: The cond to determine which component to render.
            comp1: The component to render if the cond is true.
            comp2: The component to render if the cond is false.

        Returns:
            The conditional component.
        """
        from pynecone.components.layout.foreach import Foreach

        if comp2 is None:
            comp2 = Fragment.create()
        if isinstance(comp1, Foreach):
            comp1 = Fragment.create(comp1)
        if isinstance(comp2, Foreach):
            comp2 = Fragment.create(comp2)
        if isinstance(comp1, Cond):
            comp1.is_nested = True
        if isinstance(comp2, Cond):
            comp2.is_nested = True
        return cls(
            cond=cond,
            comp1=comp1,
            comp2=comp2,
            children=[comp1, comp2],
        )  # type: ignore

    def _render(self) -> Tag:
        return CondTag(
            cond=self.cond,
            true_value=self.comp1.render(),
            false_value=self.comp2.render(),
            is_nested=self.is_nested,
        )
