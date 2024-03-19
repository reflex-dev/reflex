"""List components."""

from typing import Iterable, Literal, Optional, Union

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.foreach import Foreach
from reflex.components.el.elements.typography import Li
from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.typography.text import Text
from reflex.style import Style
from reflex.vars import Var

from .base import LayoutComponent
from .flex import Flex

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


class BaseList(Flex, LayoutComponent):
    """Base class for ordered and unordered lists."""

    # The style of the list. Default to "none".
    list_style_type: Var[
        Union[LiteralListStyleTypeUnordered, LiteralListStyleTypeOrdered]
    ]

    @classmethod
    def create(
        cls,
        *children,
        items: Optional[Union[Var[Iterable], Iterable]] = None,
        **props,
    ):
        """Create a list component.

        Args:
            *children: The children of the component.
            items: A list of items to add to the list.
            **props: The properties of the component.

        Returns:
            The list component.

        """
        list_style_type = props.pop("list_style_type", "none")
        if not children and items is not None:
            if isinstance(items, Var):
                children = [Foreach.create(items, ListItem.create)]
            else:
                children = [ListItem.create(item) for item in items]
        # props["list_style_type"] = list_style_type
        props["direction"] = "column"
        style = props.setdefault("style", {})
        style["list_style_position"] = "outside"
        style["list_style_type"] = list_style_type
        if "gap" in props:
            style["gap"] = props["gap"]
        return super().create(*children, **props)

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "direction": "column",
                "list_style_position": "outside",
                **self.style,
            }
        )


class UnorderedList(BaseList):
    """Display an unordered list."""

    @classmethod
    def create(
        cls,
        *children,
        items: Optional[Var[Iterable]] = None,
        list_style_type: LiteralListStyleTypeUnordered = "disc",
        **props,
    ):
        """Create a unordered list component.

        Args:
            *children: The children of the component.
            items: A list of items to add to the list.
            list_style_type: The style of the list.
            **props: The properties of the component.

        Returns:
            The list component.

        """
        return super().create(
            *children, items=items, list_style_type=list_style_type, **props
        )


class OrderedList(BaseList):
    """Display an ordered list."""

    @classmethod
    def create(
        cls,
        *children,
        items: Optional[Var[Iterable]] = None,
        list_style_type: LiteralListStyleTypeOrdered = "decimal",
        **props,
    ):
        """Create an ordered list component.

        Args:
            *children: The children of the component.
            items: A list of items to add to the list.
            list_style_type: The style of the list.
            **props: The properties of the component.

        Returns:
            The list component.

        """
        return super().create(
            *children, items=items, list_style_type=list_style_type, **props
        )


class ListItem(Li):
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

    item = ListItem.create
    ordered = OrderedList.create
    unordered = UnorderedList.create
