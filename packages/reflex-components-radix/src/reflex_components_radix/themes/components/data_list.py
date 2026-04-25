"""Components for the DataList component of Radix Themes."""

from types import SimpleNamespace
from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent


class DataListRoot(RadixThemesComponent):
    """Root element for a DataList component."""

    tag = "DataList.Root"

    orientation: Var[Responsive[Literal["horizontal", "vertical"]]] = field(
        doc='The orientation of the data list item: "horizontal" | "vertical"'
    )

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the data list item: "1" | "2" | "3"'
    )

    trim: Var[Responsive[Literal["normal", "start", "end", "both"]]] = field(
        doc="Trims the leading whitespace from the start or end of the text."
    )


class DataListItem(RadixThemesComponent):
    """An item in the DataList component."""

    tag = "DataList.Item"

    align: Var[Responsive[Literal["start", "center", "end", "baseline", "stretch"]]] = (
        field(doc="The alignment of the data list item within its container.")
    )


class DataListLabel(RadixThemesComponent):
    """A label in the DataList component."""

    tag = "DataList.Label"

    width: Var[Responsive[str]] = field(doc="The width of the component")

    min_width: Var[Responsive[str]] = field(doc="The minimum width of the component")

    max_width: Var[Responsive[str]] = field(doc="The maximum width of the component")

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color scheme for the DataList component."
    )


class DataListValue(RadixThemesComponent):
    """A value in the DataList component."""

    tag = "DataList.Value"


class DataList(SimpleNamespace):
    """DataList components namespace."""

    root = staticmethod(DataListRoot.create)
    item = staticmethod(DataListItem.create)
    label = staticmethod(DataListLabel.create)
    value = staticmethod(DataListValue.create)


data_list = DataList()
