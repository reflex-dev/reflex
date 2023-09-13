"""Data Editor component from glide-data-grid."""

from typing import Any, Dict

from reflex.components.component import EVENT_ARG, Component, NoSSRComponent
from reflex.components.layout import Box
from reflex.utils import console, imports
from reflex.vars import ImportVar, Var, get_unique_variable_name

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
    data: Var[list]

    # the name of the callback used to find the data to display
    getCellContent: Var[str]

    # the name of the callback when a cell is edited
    onCellEdited: Var[str]

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
                    ImportVar(tag=f"formatCell", is_default=False),
                    ImportVar(tag=f"onEditCell", is_default=False),
                },
            },
        )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the DataEditor component.

        Args:
            *children: The children of the data editor.
            **props: The props of the data editor.

        Returns:
            The DataEditor component.&
        """
        from reflex.el.elements import Div

        props.setdefault("getCellForSelection", True)

        if props.pop("getCellContent", None) is not None:
            console.warn(
                "getCellContent is not parametrable, user value will be discarded"
            )
        grid = super().create(*children, **props)
        return Box.create(grid, Div.create(id="portal"))

    def get_controlled_triggers(self) -> Dict[str, Var]:
        """The event triggers of the component.

        Returns:
            The dict describing the event triggers.
        """
        return {
            "onCellEdited": EVENT_ARG,
        }

    def _get_hooks(self) -> str | None:
        editor_id = get_unique_variable_name()
        data_callback = f"getData_{editor_id}"
        self.getCellContent = Var.create(data_callback, is_local=False)  # type: ignore

        code = [f"function {data_callback}([col, row])" "{"]

        code.extend(
            [
                f"  if (row < {self.data.full_name}.length && col < {self.columns.full_name}.length)"
                " {",
                f"    const rowData = {self.data.full_name}[row];",
                f"    const column = {self.columns.full_name}[col];"
                f"    const columnName = column.title.toLowerCase();",
                # f"    const columnType = column.type;",
                f"    const cellData = rowData[columnName];",
                "    return formatCell(cellData, column);",
                "  }",
                "  return { kind: GridCellKind.Loading};",
            ]
        )

        code.append("}")

        return "\n".join(code)
