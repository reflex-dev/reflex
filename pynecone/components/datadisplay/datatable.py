"""Table components."""

from typing import Any, List

from pynecone import utils
from pynecone.components.component import Component
from pynecone.components.tags import Tag
from pynecone.var import Var


class Gridjs(Component):
    """A component that wraps a nivo bar component."""

    library = "gridjs-react"


class DataTable(Gridjs):
    """A data table component."""

    tag = "Grid"

    df: Var[Any]

    # The data to display. EIther a list of lists or a pandas dataframe.
    data: Any

    # The columns to display.
    columns: Var[List]

    # Enable a search bar.
    search: Var[bool]

    # Enable sorting on columns.
    sort: Var[bool]

    # Enable resizable columns.
    resizable: Var[bool]

    # Enable pagination.
    pagination: Var[bool]

    def _get_custom_code(self) -> str:
        return """
import "gridjs/dist/theme/mermaid.css";
"""

    def _render(self) -> Tag:
        if utils.is_dataframe(type(self.data)):
            self.columns = Var.create(list(self.data.columns.values.tolist()))  # type: ignore
            self.data = Var.create(list(self.data.values.tolist()))  # type: ignore

        if isinstance(self.df, Var):
            self.columns = self.df["columns"]
            self.data = self.df["data"]

        return super()._render()
