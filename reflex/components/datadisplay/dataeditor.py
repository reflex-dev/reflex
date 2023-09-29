"""Data Editor component from glide-data-grid."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

# GridColumnIcons
#  HeaderArray
#  HeaderAudioUri
#  HeaderBoolean
#  HeaderCode
#  HeaderDate
#  HeaderEmail
#  HeaderEmoji
#  HeaderGeoDistance
#  HeaderIfThenElse
#  HeaderImage
#  HeaderJoinStrings
#  HeaderLookup
#  HeaderMarkdown
#  HeaderMath
#  HeaderNumber
#  HeaderPhone
#  HeaderReference
#  HeaderRollup
#  HeaderRowID
#  HeaderSingleValue
#  HeaderSplitString
#  HeaderString
#  HeaderTextTemplate
#  HeaderTime
#  HeaderUri
#  HeaderVideoUri
from icecream import ic

from reflex.base import Base
from reflex.components.component import Component, NoSSRComponent
from reflex.components.layout import Box
from reflex.utils import console, format, imports, types
from reflex.vars import BaseVar, ImportVar, Var, get_unique_variable_name


class DataEditorColumn(Base):
    """Column."""

    title: str
    id: Optional[str] = None
    type: str = "str"


class DataEditor(NoSSRComponent):
    """The DataEditor Component."""

    tag = "DataEditor"
    library: str = "@glideapps/glide-data-grid"
    lib_dependencies: list[str] = ["lodash", "marked", "react-responsive-carousel"]

    # number of rows
    rows: Var[int]
    # headers of the columns for the data grid
    columns: Var[list[dict[str, Any]]]

    # the data
    data: Var[Any]

    # the name of the callback used to find the data to display
    getCellContent: Var[str]

    # allow copy paste or not
    getCellForSelection: Var[bool]

    is_default = True

    def _get_imports(self):
        return imports.merge_imports(
            super()._get_imports(),
            {
                "": {ImportVar(tag=f"{self.library}/dist/index.css")},
                self.library: {ImportVar(tag="GridCellKind")},
                "/utils/helpers/dataeditor.js": {
                    ImportVar(tag=f"getDEColumn", is_default=False, install=False),
                    ImportVar(tag=f"getDERow", is_default=False, install=False),
                    ImportVar(tag=f"locateCell", is_default=False, install=False),
                    ImportVar(tag=f"formatCell", is_default=False, install=False),
                    ImportVar(tag=f"onEditCell", is_default=False, install=False),
                },
            },
        )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the DataEditor component.

        Args:
            *children: The children of the data editor.
            **props: The props of the data editor.

        Raises:
            ValueError: invalid input.

        Returns:
            The DataEditor component.&
        """
        from reflex.el.elements import Div

        columns = props.get("columns", [])
        data = props.get("data", [])
        rows = props.get("rows", None)
        # if rows is not provided, determine from data
        if rows is None:
            props["rows"] = (
                BaseVar.create(value=f"{data}.length()", is_local=False)
                if isinstance(data, Var)
                else len(data)
            )

        if not isinstance(columns, Var) and len(columns):
            if (
                types.is_dataframe(type(data))
                or isinstance(data, Var)
                and types.is_dataframe(data.type_)
            ):
                raise ValueError(
                    "Cannot pass in both a pandas dataframe and columns to the data_editor component."
                )
            else:
                props["columns"] = [
                    format.format_data_editor_column(col) for col in columns
                ]

        if isinstance(data, Var):
            ic(data.type_)

        props.setdefault("getCellForSelection", True)

        if props.pop("getCellContent", None) is not None:
            console.warn(
                "getCellContent is not parametrable, user value will be discarded"
            )
        grid = super().create(*children, **props)
        return Box.create(grid, Div.create(id="portal"))

    def get_event_triggers(self) -> Dict[str, Callable]:
        """The event triggers of the component.

        Returns:
            The dict describing the event triggers.
        """
        return {
            "onCellEdited": lambda pos, data: [pos, data],
        }

    def _get_hooks(self) -> str | None:
        editor_id = get_unique_variable_name()
        data_callback = f"getData_{editor_id}"
        self.getCellContent = Var.create(data_callback, is_local=False)  # type: ignore

        code = [f"function {data_callback}([col, row])" "{"]
        # ic(self.columns, self.data)

        code.extend(
            [
                f"  if (row < {self.data.full_name}.length && col < {self.columns.full_name}.length)"
                " {",
                f"    const column = getDEColumn({self.columns.full_name}, col);",
                f"    const rowData = getDERow({self.data.full_name}, row);",
                f"    const cellData = locateCell(rowData, column);",
                "    return formatCell(cellData, column);",
                "  }",
                "  return { kind: GridCellKind.Loading};",
            ]
        )

        code.append("}")

        return "\n".join(code)

    # def _render(self) -> Tag:
    #     if isinstance(self.data, Var) and types.is_dataframe(self.data.type_):
    #         self.columns = BaseVar(
    #             name=f"{self.data.name}.columns",
    #             type_=List[Any],
    #             state=self.data.state,
    #         )
    #         self.data = BaseVar(
    #             name=f"{self.data.name}.data",
    #             type_=List[List[Any]],
    #             state=self.data.state,
    #         )
    #     if types.is_dataframe(type(self.data)):
    #         # If given a pandas df break up the data and columns
    #         data = serialize(self.data)
    #         assert isinstance(data, dict), "Serialized dataframe should be a dict."
    #         self.columns = Var.create_safe(data["columns"])
    #         self.data = Var.create_safe(data["data"])

    #    # Render the table.
    #    return super()._render()


# try:
#     pass

#     # def format_dataframe_values(df: DataFrame) -> list[list[Any]]:
#     #     """Format dataframe values to a list of lists.

#     #     Args:
#     #         df: The dataframe to format.

#     #     Returns:
#     #         The dataframe as a list of lists.
#     #     """
#     # return [
#     #     [str(d) if isinstance(d, (list, tuple)) else d for d in data]
#     #     for data in list(df.values.tolist())
#     # ]
#     # ...

#     # @serializer
#     # def serialize_dataframe(df: DataFrame) -> dict:
#     #     """Serialize a pandas dataframe.

#     #     Args:
#     #         df: The dataframe to serialize.

#     #     Returns:
#     #         The serialized dataframe.
#     #     """
#     # return {
#     #     "columns": df.columns.tolist(),
#     #     "data": format_dataframe_values(df),
#     # }

# except ImportError:
#     pass
