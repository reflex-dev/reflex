"""A container that bounds the width of a page."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.style import ComponentStyles, StyleError
from reflex_components_ui.styles.container import CONTAINER

LiteralContainerSize = Literal["1", "2", "3", "4"]


class Container(UIComponent, elements.Div):
    """Constrains the maximum width of page content."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = CONTAINER

    size: Var[Responsive[LiteralContainerSize]] = field(
        default=LiteralVar.create("3"),
        doc='The size of the container: "1" - "4" (default "3")',
    )

    @classmethod
    def create(
        cls,
        *children,
        padding: str = "16px",
        stack_children_full_width: bool = False,
        **props,
    ) -> Component:
        """Create the container component.

        Args:
            *children: The children components.
            padding: The padding of the container.
            stack_children_full_width: If True, any vstack/hstack children will have 100% width.
            **props: The properties of the container.

        Returns:
            The container component.

        Raises:
            StyleError: If ``stack_children_full_width`` is set: it styles the
                stacks inside the container through nested selectors.
        """
        if stack_children_full_width:
            msg = (
                f"{cls._display_name()}: stack_children_full_width styles the "
                "stacks inside the container through nested selectors, which "
                'rx.ui styles do not support. Give those stacks width="100%", '
                "or keep rx.container for this element."
            )
            raise StyleError(msg)
        return super().create(
            Part.create(*children, part="inner", tag="div"),
            padding=padding,
            **props,
        )


container = Container.create
