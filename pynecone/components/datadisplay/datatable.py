"""Table components."""

from typing import Any, List

from pynecone import utils
from pynecone.components.component import Component, ImportDict
from pynecone.components.tags import Tag
from pynecone.var import Var


class Gridjs(Component):
    """A component that wraps a nivo bar component."""

    library = "gridjs-react"


class DataTable(Gridjs):
    """A data table component."""

    tag = "Grid"

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

    def _get_imports(self) -> ImportDict:
        return utils.merge_imports(
            super()._get_imports(), {"": {"gridjs/dist/theme/mermaid.css"}}
        )

    def _render(self) -> Tag:
        if utils.is_dataframe(type(self.data)):
            # If given a pandas df break up the data and columns
            self.columns = Var.create(list(self.data.columns.values.tolist()))  
            self.data = Var.create(list(self.data.values.tolist()))
            
        return super()._render()
