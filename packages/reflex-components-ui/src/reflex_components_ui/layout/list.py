"""List components."""

from __future__ import annotations

from collections.abc import Iterable, MutableSequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.vars.base import Var
from reflex_components_core.core.foreach import Foreach
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el.elements.base import BaseHTML
from reflex_components_core.el.elements.typography import Li, Ol, Ul
from reflex_components_lucide.icon import Icon

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.list import LIST, MARKER_INDENT
from reflex_components_ui.typography.text import Text

LiteralListStyleTypeUnordered = Literal[
    "none",
    "disc",
    "circle",
    "square",
]

LiteralListStyleTypeOrdered = Literal[
    "none",
    "decimal",
    "decimal-leading-zero",
    "lower-roman",
    "upper-roman",
    "lower-greek",
    "lower-latin",
    "upper-latin",
    "armenian",
    "georgian",
    "lower-alpha",
    "upper-alpha",
    "hiragana",
    "katakana",
]


class BaseList(UIComponent, BaseHTML, MarkdownComponentMap):
    """Base class for ordered and unordered lists."""

    tag = "ul"

    styles: ClassVar[ComponentStyles] = LIST

    list_style_type: Var[
        LiteralListStyleTypeUnordered | LiteralListStyleTypeOrdered
    ] = field(
        default=Var.create("none"), doc='The style of the list. Default to "none".'
    )

    items: Var[Iterable] = field(
        default=Var.create([]), doc="A list of items to add to the list."
    )

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create a list component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The list component.
        """
        items = props.pop("items", None)
        list_style_type = props.pop("list_style_type", "none")

        if not children and items is not None:
            if isinstance(items, Var):
                children = [Foreach.create(items, ListItem.create)]
            else:
                children = [ListItem.create(item) for item in items]
        # The marker wins over a list_style_type in the style of the element.
        marker: dict[str, Any] = {"list_style_type": list_style_type}
        style = props.get("style")
        if style is None:
            props["style"] = marker
        elif isinstance(style, (list, tuple)):
            props["style"] = [*style, marker]
        else:
            props["style"] = [style, marker]
        return super().create(*children, **props)

    def _exclude_props(self) -> MutableSequence[str]:
        return [*super()._exclude_props(), "items", "list_style_type"]


class UnorderedList(BaseList, Ul):
    """Display an unordered list."""

    tag = "ul"

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create an unordered list component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The list component.
        """
        items = props.pop("items", None)
        list_style_type = props.pop("list_style_type", "disc")

        props["margin_left"] = props.get("margin_left", MARKER_INDENT)
        return super().create(
            *children, items=items, list_style_type=list_style_type, **props
        )


class OrderedList(BaseList, Ol):
    """Display an ordered list."""

    tag = "ol"

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create an ordered list component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The list component.
        """
        items = props.pop("items", None)
        list_style_type = props.pop("list_style_type", "decimal")

        props["margin_left"] = props.get("margin_left", MARKER_INDENT)
        return super().create(
            *children, items=items, list_style_type=list_style_type, **props
        )


class ListItem(UIComponent, Li, MarkdownComponentMap):
    """Display an item of an ordered or unordered list."""

    tag = "li"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a list item component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The list item component.
        """
        for child in children:
            if isinstance(child, Text):
                # Text inside an item is a run of it, not a paragraph.
                child.tag = "span"
            elif isinstance(child, Icon) and "display" not in child.style:
                child.style["display"] = "inline"
        return super().create(*children, **props)


class List(ComponentNamespace):
    """List components."""

    item = staticmethod(ListItem.create)
    ordered = staticmethod(OrderedList.create)
    unordered = staticmethod(UnorderedList.create)
    __call__ = staticmethod(BaseList.create)


list_ns = List()
list_item = list_ns.item
ordered_list = list_ns.ordered
unordered_list = list_ns.unordered
