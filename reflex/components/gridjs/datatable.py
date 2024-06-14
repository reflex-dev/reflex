"""Table components."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from reflex.components.component import Component
from reflex.components.tags import Tag
from reflex.utils import types
from reflex.utils.imports import ImportDict
from reflex.utils.serializers import serialize
from reflex.vars import BaseVar, ComputedVar, Var


class Gridjs(Component):
    """A component that wraps a nivo bar component."""

    library = "gridjs-react@6.0.1"

    lib_dependencies: List[str] = ["gridjs@6.0.6"]


class DataTable(Gridjs):
    """A data table component."""

    tag = "Grid"

    alias = "DataTableGrid"

    # The data to display. Either a list of lists or a pandas dataframe.
    data: Any

    # The list of columns to display. Required if data is a list and should not be provided
    # if the data field is a dataframe
    columns: Var[List]

    # Enable a search bar.
    search: Var[bool]

    # Enable sorting on columns.
    sort: Var[bool]

    # Enable resizable columns.
    resizable: Var[bool]

    # Enable pagination.
    pagination: Var[Union[bool, Dict]]

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
        data = props.get("data")
        columns = props.get("columns")

        # The annotation should be provided if data is a computed var. We need this to know how to
        # render pandas dataframes.
        if isinstance(data, ComputedVar) and data._var_type == Any:
            raise ValueError(
                "Annotation of the computed var assigned to the data field should be provided."
            )

        if (
            columns is not None
            and isinstance(columns, ComputedVar)
            and columns._var_type == Any
        ):
            raise ValueError(
                "Annotation of the computed var assigned to the column field should be provided."
            )

        # If data is a pandas dataframe and columns are provided throw an error.
        if (
            types.is_dataframe(type(data))
            or (isinstance(data, Var) and types.is_dataframe(data._var_type))
        ) and columns is not None:
            raise ValueError(
                "Cannot pass in both a pandas dataframe and columns to the data_table component."
            )

        # If data is a list and columns are not provided, throw an error
        if (
            (isinstance(data, Var) and types._issubclass(data._var_type, List))
            or issubclass(type(data), List)
        ) and columns is None:
            raise ValueError(
                "column field should be specified when the data field is a list type"
            )

        # Create the component.
        return super().create(
            *children,
            **props,
        )

    def add_imports(self) -> ImportDict:
        """Add the imports for the datatable component.

        Returns:
            The import dict for the component.
        """
        return {"": "gridjs/dist/theme/mermaid.css"}

    def _render(self) -> Tag:
        if isinstance(self.data, Var) and types.is_dataframe(self.data._var_type):
            self.columns = BaseVar(
                _var_name=f"{self.data._var_name}.columns",
                _var_type=List[Any],
                _var_full_name_needs_state_prefix=True,
                _var_data=self.data._var_data,
            )
            self.data = BaseVar(
                _var_name=f"{self.data._var_name}.data",
                _var_type=List[List[Any]],
                _var_full_name_needs_state_prefix=True,
                _var_data=self.data._var_data,
            )
        if types.is_dataframe(type(self.data)):
            # If given a pandas df break up the data and columns
            data = serialize(self.data)
            assert isinstance(data, dict), "Serialized dataframe should be a dict."
            self.columns = Var.create_safe(data["columns"])
            self.data = Var.create_safe(data["data"])

        # Render the table.
        return super()._render()
