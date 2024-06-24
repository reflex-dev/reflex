"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

from reflex.components.el import elements
from reflex.style import STACK_CHILDREN_FULL_WIDTH
from reflex.vars import Var

from ..base import RadixThemesComponent

LiteralContainerSize = Literal["1", "2", "3", "4"]


class Container(elements.Div, RadixThemesComponent):
    """Constrains the maximum width of page content.

    See https://www.radix-ui.com/themes/docs/components/container
    """

    tag = "Container"

    # The size of the container: "1" - "4" (default "3")
    size: Var[LiteralContainerSize] = Var.create_safe("3", _var_is_string=True)

    @classmethod
    def create(
        cls,
        *children,
        padding: str = "16px",
        stack_children_full_width: bool = False,
        **props,
    ):
        """Create the container component.

        Args:
            children: The children components.
            padding: The padding of the container.
            stack_children_full_width: If True, any vstack/hstack children will have 100% width.
            props: The properties of the container.

        Returns:
            The container component.
        """
        if stack_children_full_width:
            props["style"] = {**STACK_CHILDREN_FULL_WIDTH, **props.pop("style", {})}
        return super().create(
            *children,
            padding=padding,
            **props,
        )


container = Container.create
