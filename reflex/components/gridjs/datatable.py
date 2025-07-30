"""Table components."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from reflex.components.component import NoSSRComponent
from reflex.components.tags import Tag
from reflex.utils import types
from reflex.utils.imports import ImportDict
from reflex.utils.serializers import serialize
from reflex.vars.base import LiteralVar, Var, is_computed_var


class Gridjs(NoSSRComponent):
    """A component that wraps a nivo bar component."""

    library = "gridjs-react@6.1.1"

    lib_dependencies: list[str] = ["gridjs@6.2.0"]


class DataTable(Gridjs):
    """A data table component."""

    tag = "Grid"

    alias = "DataTableGrid"

    # The data to display. Either a list of lists or a pandas dataframe.
    data: Any

    # The list of columns to display. Required if data is a list and should not be provided
    # if the data field is a dataframe
    columns: Var[Sequence]

    # Enable a search bar.
    search: Var[bool]

    # Enable sorting on columns.
    sort: Var[bool]

    # Enable resizable columns.
    resizable: Var[bool]

    # Enable pagination.
    pagination: Var[bool | dict]

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
        if is_computed_var(data) and data._var_type == Any:
            msg = "Annotation of the computed var assigned to the data field should be provided."
            raise ValueError(msg)

        if (
            columns is not None
            and is_computed_var(columns)
            and columns._var_type == Any
        ):
            msg = "Annotation of the computed var assigned to the column field should be provided."
            raise ValueError(msg)

        # If data is a pandas dataframe and columns are provided throw an error.
        if (
            types.is_dataframe(type(data))
            or (isinstance(data, Var) and types.is_dataframe(data._var_type))
        ) and columns is not None:
            msg = "Cannot pass in both a pandas dataframe and columns to the data_table component."
            raise ValueError(msg)

        # If data is a list and columns are not provided, throw an error
        if (
            (isinstance(data, Var) and types.typehint_issubclass(data._var_type, list))
            or isinstance(data, list)
        ) and columns is None:
            msg = "column field should be specified when the data field is a list type"
            raise ValueError(msg)

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
            self.columns = self.data._replace(
                _js_expr=f"{self.data._js_expr}.columns",
                _var_type=list[Any],
            )
            self.data = self.data._replace(
                _js_expr=f"{self.data._js_expr}.data",
                _var_type=list[list[Any]],
            )
        if types.is_dataframe(type(self.data)):
            # If given a pandas df break up the data and columns
            data = serialize(self.data)
            if not isinstance(data, dict):
                msg = "Serialized dataframe should be a dict."
                raise ValueError(msg)
            self.columns = LiteralVar.create(data["columns"])
            self.data = LiteralVar.create(data["data"])

        # Render the table.
        return super()._render()
