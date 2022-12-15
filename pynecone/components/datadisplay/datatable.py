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

    @classmethod
    def create(cls, *children, **props):
        """Create a datatable component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The datatable component.

        Raises:
            ValueError: If a pandas dataframe is passed in and columns are also provided.
        """
        # If data is a pandas dataframe and columns are provided throw an error.
        if utils.is_dataframe(type(props.get("data"))) and props.get("columns"):
            raise ValueError(
                "Cannot pass in both a pandas dataframe and columns to the data_table component."
            )

        # Create the component.
        return super().create(
            *children,
            **props,
        )

    def _get_imports(self) -> ImportDict:
        return utils.merge_imports(
            super()._get_imports(), {"": {"gridjs/dist/theme/mermaid.css"}}
        )

    def _render(self) -> Tag:
        if utils.is_dataframe(type(self.data)):
            # If given a pandas df break up the data and columns
            self.columns = Var.create(list(self.data.columns.values.tolist()))  # type: ignore
            self.data = Var.create(list(self.data.values.tolist()))  # type: ignore

        return super()._render()
