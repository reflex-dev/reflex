"""List components."""

from __future__ import annotations

from typing import Any, Iterable, Literal, Union

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.foreach import Foreach
from reflex.components.el.elements.typography import Li, Ol, Ul
from reflex.components.lucide.icon import Icon
from reflex.components.markdown.markdown import MarkdownComponentMap
from reflex.components.radix.themes.typography.text import Text
from reflex.vars.base import Var

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


class BaseList(Component, MarkdownComponentMap):
    """Base class for ordered and unordered lists."""

    tag = "ul"

    # The style of the list. Default to "none".
    list_style_type: Var[
        Union[LiteralListStyleTypeUnordered, LiteralListStyleTypeOrdered]
    ] = Var.create("none")

    # A list of items to add to the list.
    items: Var[Iterable] = Var.create([])

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ):
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
                children = [ListItem.create(item) for item in items]  # type: ignore
        props["direction"] = "column"
        style = props.setdefault("style", {})
        style["list_style_type"] = list_style_type
        if "gap" in props:
            style["gap"] = props["gap"]
        return super().create(*children, **props)

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {
            "direction": "column",
        }

    def _exclude_props(self) -> list[str]:
        return ["items", "list_style_type"]


class UnorderedList(BaseList, Ul):
    """Display an unordered list."""

    tag = "ul"

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ):
        """Create an unordered list component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The list component.
        """
        items = props.pop("items", None)
        list_style_type = props.pop("list_style_type", "disc")

        props["margin_left"] = props.get("margin_left", "1.5rem")
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
    ):
        """Create an ordered list component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The list component.
        """
        items = props.pop("items", None)
        list_style_type = props.pop("list_style_type", "decimal")

        props["margin_left"] = props.get("margin_left", "1.5rem")
        return super().create(
            *children, items=items, list_style_type=list_style_type, **props
        )


class ListItem(Li, MarkdownComponentMap):
    """Display an item of an ordered or unordered list."""

    @classmethod
    def create(cls, *children, **props):
        """Create a list item component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The list item component.
        """
        for child in children:
            if isinstance(child, Text):
                child.as_ = "span"
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


def __getattr__(name):
    # special case for when accessing list to avoid shadowing
    # python's built in list object.
    if name == "list":
        return list_ns
    try:
        return globals()[name]
    except KeyError:
        raise AttributeError(f"module '{__name__} has no attribute '{name}'") from None
