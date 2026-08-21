"""An accordion built on native details and summary elements.

Exclusive (one-item-open) behavior uses the details ``name`` attribute, so
no JavaScript is required.
"""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import BaseComponent, ComponentNamespace, field
from reflex_base.vars.base import Var, get_unique_variable_name

from reflex_components_core.el.elements import other
from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui._icons import chevron_down
from reflex_components_core.ui.base import UIComponent

ACCORDION_CLASS_NAME = "w-full"

ACCORDION_ITEM_CLASS_NAME = "group border-b border-border last:border-b-0"

ACCORDION_TRIGGER_CLASS_NAME = (
    "flex flex-1 items-center justify-between gap-4 rounded-md py-4 "
    "text-left text-sm font-medium transition-all outline-none cursor-pointer "
    "list-none [&::-webkit-details-marker]:hidden hover:underline "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
)

ACCORDION_ICON_CLASS_NAME = (
    "text-muted-foreground pointer-events-none size-4 shrink-0 "
    "transition-transform duration-200 group-open:rotate-180"
)

ACCORDION_CONTENT_CLASS_NAME = "overflow-hidden pb-4 pt-0 text-sm"


class AccordionItem(other.Details, UIComponent):
    """A single expandable accordion item."""

    _slot: ClassVar[str | None] = "accordion-item"

    name: Var[str] = field(
        doc="Group name shared by exclusive accordion items; set by the root."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create an accordion item.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The accordion item component.
        """
        cls._apply_class_name(ACCORDION_ITEM_CLASS_NAME, props)
        return super().create(*children, **props)


class AccordionTrigger(other.Summary, UIComponent):
    """The always-visible summary that toggles an accordion item."""

    _slot: ClassVar[str | None] = "accordion-trigger"

    @classmethod
    def create(cls, *children, **props):
        """Create an accordion trigger with its indicator icon.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The accordion trigger component.
        """
        unstyled = props.get("unstyled", False)
        cls._apply_class_name(ACCORDION_TRIGGER_CLASS_NAME, props)
        icon = [] if unstyled else [chevron_down(class_name=ACCORDION_ICON_CLASS_NAME)]
        return super().create(*children, *icon, **props)


class AccordionContent(Div, UIComponent):
    """The collapsible content of an accordion item."""

    _slot: ClassVar[str | None] = "accordion-content"

    @classmethod
    def create(cls, *children, **props):
        """Create accordion content.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The accordion content component.
        """
        cls._apply_class_name(ACCORDION_CONTENT_CLASS_NAME, props)
        return super().create(*children, **props)


def _assign_group_name(component: BaseComponent, name: str) -> None:
    """Assign a shared group name to accordion items in a subtree.

    Args:
        component: The component to walk.
        name: The group name to assign.
    """
    for child in component.children:
        if isinstance(child, AccordionItem):
            if child.name is None:
                child.name = name  # pyright: ignore[reportAttributeAccessIssue]
        elif isinstance(child, Accordion):
            continue
        if isinstance(child, BaseComponent):
            _assign_group_name(child, name)


class Accordion(Div, UIComponent):
    """A vertically stacked set of expandable items.

    Items are exclusive by default (opening one closes the others), using
    the native details grouping behavior. Pass ``multiple=True`` to allow
    several items open at once.
    """

    _slot: ClassVar[str | None] = "accordion"

    multiple: Var[bool] = field(
        doc="Allow multiple items to be open at once. Defaults to False."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create an accordion.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The accordion component.

        Raises:
            TypeError: If multiple is not a static bool.
        """
        multiple = props.pop("multiple", False)
        if isinstance(multiple, Var):
            msg = "The multiple prop must be a static bool, not a Var."
            raise TypeError(msg)
        cls._apply_class_name(ACCORDION_CLASS_NAME, props)
        component = super().create(*children, **props)
        if not multiple:
            _assign_group_name(component, f"accordion-{get_unique_variable_name()}")
        return component

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "multiple",
        ]


class AccordionNamespace(ComponentNamespace):
    """Namespace for accordion components."""

    root = staticmethod(Accordion.create)
    item = staticmethod(AccordionItem.create)
    trigger = staticmethod(AccordionTrigger.create)
    content = staticmethod(AccordionContent.create)
    __call__ = staticmethod(Accordion.create)


accordion = AccordionNamespace()
