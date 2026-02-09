"""Table components for Reflex using Gridjs."""

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
    """A base component that wraps Gridjs (JS library) for tables."""

    library = "gridjs-react@6.1.1"
    lib_dependencies: list[str] = ["gridjs@6.2.0"]


class DataTable(Gridjs):
    """A flexible data table component for Reflex.

    Supports:
    - Pandas DataFrames
    - Python lists
    - Reflex Vars (state variables)
    """

    tag = "Grid"
    alias = "DataTableGrid"

    # -----------------------------
    # Component Props
    # -----------------------------
    data: Any  # The data to display (list of lists or DataFrame)
    columns: Var[Sequence]  # Columns to display (optional if using DataFrame)
    search: Var[bool]  # Enable search
    sort: Var[bool]  # Enable sorting
    resizable: Var[bool]  # Enable column resizing
    pagination: Var[bool | dict]  # Enable pagination

    # -----------------------------
    # Component creation
    # -----------------------------
    @classmethod
    def create(cls, *children, **props):
        """Create a DataTable component with proper validation.

        Raises:
            ValueError: If both DataFrame and columns are provided, or
                        if columns are missing for a list-type data field.

        Returns:
            DataTable: The created DataTable component.
        """
        data = props.get("data")
        columns = props.get("columns")

        # 1️⃣ Ensure computed Vars have type annotations
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

        # 2️⃣ Disallow DataFrame + columns (columns auto-detected from DataFrame)
        if (
            types.is_dataframe(type(data))
            or (isinstance(data, Var) and types.is_dataframe(data._var_type))
        ) and columns is not None:
            msg = "Cannot pass in both a pandas dataframe and columns to the data_table component."
            raise ValueError(msg)

        # 3️⃣ Require columns if data is a list
        if (
            (isinstance(data, Var) and types.typehint_issubclass(data._var_type, list))
            or isinstance(data, list)
        ) and columns is None:
            msg = "Column field should be specified when the data field is a list type"
            raise ValueError(msg)

        # 4️⃣ Call parent create method
        return super().create(*children, **props)

    # -----------------------------
    # Add external imports (CSS)
    # -----------------------------
    def add_imports(self) -> ImportDict:
        """Add CSS for Gridjs.

        Returns:
            ImportDict: The import dictionary required for the component.
        """
        return {"": "gridjs/dist/theme/mermaid.css"}

    # -----------------------------
    # Render component
    # -----------------------------
    def _render(self) -> Tag:
        """Normalize columns and prepare data for front-end rendering.

        Returns:
            Tag: The rendered table component.
        """
        # -----------------------------
        # Case 1: DataFrame coming from State (Var)
        # -----------------------------
        if isinstance(self.data, Var) and types.is_dataframe(self.data._var_type):
            # Convert DataFrame to front-end-safe Vars
            self.columns = self.data._replace(
                _js_expr=f"{self.data._js_expr}.columns",
                _var_type=list[Any],
            )
            self.data = self.data._replace(
                _js_expr=f"{self.data._js_expr}.data",
                _var_type=list[list[Any]],
            )

        # -----------------------------
        # Case 2: DataFrame passed directly from Python
        # -----------------------------
        if types.is_dataframe(type(self.data)):
            data = serialize(self.data)
            if not isinstance(data, dict):
                msg = "Serialized dataframe should be a dict."
                raise ValueError(msg)

            # Convert Python lists to LiteralVars for front-end rendering
            self.columns = LiteralVar.create(data["columns"])
            self.data = LiteralVar.create(data["data"])

        # -----------------------------
        # Case 3: Normalize columns for all other scenarios
        # -----------------------------
        if self.columns is not None:
            # Python list → LiteralVar
            if isinstance(self.columns, list):
                self.columns = LiteralVar.create([
                    {"id": col, "name": col} if isinstance(col, str) else col
                    for col in self.columns
                ])

            # LiteralVar[list] → normalized LiteralVar
            elif isinstance(self.columns, LiteralVar) and isinstance(
                self.columns._var_value, list
            ):
                self.columns = LiteralVar.create([
                    {"id": col, "name": col} if isinstance(col, str) else col
                    for col in self.columns._var_value
                ])

            # Var[list] → frontend-safe JS mapping (compile-time + runtime safe)
            elif isinstance(self.columns, Var):
                self.columns = self.columns._replace(
                    _js_expr=(
                        f"{self.columns._js_expr}.map("
                        "(col) => typeof col === 'string' "
                        "? ({ id: col, name: col }) "
                        ": col)"
                    ),
                    _var_type=list[Any],
                )

        # -----------------------------
        # Case 4: Render component
        # -----------------------------
        return super()._render()
