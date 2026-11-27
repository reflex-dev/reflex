"""A data list: labels and their values."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.base import UIComponent
from reflex_components_ui.props import style_props
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.data_list import (
    DATA_LIST_ITEM,
    DATA_LIST_LABEL,
    DATA_LIST_ROOT,
    DATA_LIST_VALUE,
)
from reflex_components_ui.themes import LiteralAccentColor


class DataListRoot(UIComponent):
    """Root element for a DataList component."""

    tag = "dl"

    styles: ClassVar[ComponentStyles] = DATA_LIST_ROOT

    orientation: Var[Responsive[Literal["horizontal", "vertical"]]] = field(
        doc='The orientation of the data list item: "horizontal" | "vertical"'
    )

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the data list item: "1" | "2" | "3"'
    )

    trim: Var[Responsive[Literal["normal", "start", "end", "both"]]] = field(
        doc="Trims the leading whitespace from the start or end of the text."
    )


class DataListItem(UIComponent):
    """An item in the DataList component."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = DATA_LIST_ITEM

    align: Var[Responsive[Literal["start", "center", "end", "baseline", "stretch"]]] = (
        field(doc="The alignment of the data list item within its container.")
    )


class DataListLabel(UIComponent):
    """A label in the DataList component."""

    tag = "dt"

    styles: ClassVar[ComponentStyles] = DATA_LIST_LABEL

    width: Var[Responsive[str]] = field(doc="The width of the component")

    min_width: Var[Responsive[str]] = field(doc="The minimum width of the component")

    max_width: Var[Responsive[str]] = field(doc="The maximum width of the component")

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color scheme for the DataList component."
    )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a label, as wide as its width props say.

        Args:
            *children: The children of the label.
            **props: The props of the label.

        Returns:
            The label.
        """
        style_props("rx.ui.data_list.label", props, ("width", "min_width", "max_width"))
        return super().create(*children, **props)


class DataListValue(UIComponent):
    """A value in the DataList component."""

    tag = "dd"

    styles: ClassVar[ComponentStyles] = DATA_LIST_VALUE


class DataList(ComponentNamespace):
    """DataList components namespace."""

    root = staticmethod(DataListRoot.create)
    item = staticmethod(DataListItem.create)
    label = staticmethod(DataListLabel.create)
    value = staticmethod(DataListValue.create)


data_list = DataList()
