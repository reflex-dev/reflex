"""Components for the DataList component of Radix Themes."""

from types import SimpleNamespace
from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import LiteralAccentColor, RadixThemesComponent
from reflex.vars.base import Var


class DataListRoot(RadixThemesComponent):
    """Root element for a DataList component."""

    tag = "DataList.Root"

    # The orientation of the data list item: "horizontal" | "vertical"
    orientation: Var[Responsive[Literal["horizontal", "vertical"]]]

    # The size of the data list item: "1" | "2" | "3"
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # Trims the leading whitespace from the start or end of the text.
    trim: Var[Responsive[Literal["normal", "start", "end", "both"]]]


class DataListItem(RadixThemesComponent):
    """An item in the DataList component."""

    tag = "DataList.Item"

    # The alignment of the data list item within its container.
    align: Var[Responsive[Literal["start", "center", "end", "baseline", "stretch"]]]


class DataListLabel(RadixThemesComponent):
    """A label in the DataList component."""

    tag = "DataList.Label"

    # The width of the component
    width: Var[Responsive[str]]

    # The minimum width of the component
    min_width: Var[Responsive[str]]

    # The maximum width of the component
    max_width: Var[Responsive[str]]

    # The color scheme for the DataList component.
    color_scheme: Var[LiteralAccentColor]


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
