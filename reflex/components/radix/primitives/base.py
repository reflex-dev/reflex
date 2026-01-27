"""The base component for Radix primitives."""

from typing import Any

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
                class_name=f"{format.to_title_case(self.tag or '')} {self.class_name or ''}"
            )
        )


class RadixPrimitiveTriggerComponent(RadixPrimitiveComponent):
    """Base class for Trigger, Close, Cancel, and Accept components.

    These components trigger some action in an overlay component that depends on the
    on_click event, and thus if a child is provided and has on_click specified, it
    will overtake the internal action, unless it is wrapped in some inert component,
    in this case, a Flex.
    """

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a new RadixPrimitiveTriggerComponent instance.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The new RadixPrimitiveTriggerComponent instance.
        """
        from reflex.components.el.elements.typography import Div

        for child in children:
            if "on_click" in getattr(child, "event_triggers", {}):
                children = (Div.create(*children),)
                break
        return super().create(*children, **props)
