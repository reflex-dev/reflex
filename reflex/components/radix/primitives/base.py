"""The base component for Radix primitives."""

from reflex.components.component import Component
from reflex.components.tags.tag import Tag
from reflex.utils import format
from reflex.vars.base import Var


class RadixPrimitiveComponent(Component):
    """Basic component for radix Primitives."""

    # Change the default rendered element for the one passed as a child.
    as_child: Var[bool]


class RadixPrimitiveComponentWithClassName(RadixPrimitiveComponent):
    """Basic component for radix Primitives with a class name prop."""

    def _render(self) -> Tag:
        return (
            super()
            ._render()
            .add_props(
                **{
                    "class_name": f"{format.to_title_case(self.tag or '')} {self.class_name or ''}",
                }
            )
        )
