"""Data Editor component from glide-data-grid."""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List

from reflex.components.component import Component, NoSSRComponent
from reflex.components.layout import Fragment
from reflex.utils import console, format, imports, types
from reflex.vars import ImportVar, Var, get_unique_variable_name


# TODO: Fix the serialization issue for custom types.
class GridColumnIcons(Enum):
    """An Enum for the available icons in DataEditor."""

    Array = "array"
    AudioUri = "audio_uri"
    Boolean = "boolean"
    HeaderCode = "code"
    Date = "date"
    Email = "email"
    Emoji = "emoji"
    GeoDistance = "geo_distance"
    IfThenElse = "if_then_else"
    Image = "image"
    JoinStrings = "join_strings"
    Lookup = "lookup"
    Markdown = "markdown"
    Math = "math"
    Number = "number"
    Phone = "phone"
    Reference = "reference"
    Rollup = "rollup"
    RowID = "row_id"
    SingleValue = "single_value"
    SplitString = "split_string"
    String = "string"
    TextTemplate = "text_template"
    Time = "time"
    Uri = "uri"
    VideoUri = "video_uri"


# replace below with Literal
# class GridRowMarkers(str, Enum):
#     """Grid Row Markers."""

#     NUMBER = "number"
#     NONE = "none"
#     CHECKBOX = "checkbox"
#     BOTH = "both"
#     CLICKABLE_NUMBER = "clickable-number"


# @serializer
# def serialize_gridcolumn_icon(icon: GridColumnIcons) -> str:
#     """Serialize grid column icon.

#     Args:
#         icon: the Icon to serialize.

#     Returns:
#         The serialized value.
#     """
#     return "prefix" + str(icon)


# class DataEditorColumn(Base):
#     """Column."""

#     title: str
#     id: Optional[str] = None
#     type_: str = "str"


class DataEditor(NoSSRComponent):
    """The DataEditor Component."""

    tag = "DataEditor"
    is_default = True
    library: str = "@glideapps/glide-data-grid@^5.3.0"
    lib_dependencies: List[str] = ["lodash", "marked", "react-responsive-carousel"]

    # number of rows
    rows: Var[int]

    # headers of the columns for the data grid
    columns: Var[List[Dict[str, Any]]]

    # the data
    data: Var[Any]

    # the name of the callback used to find the data to display
    get_cell_content: Var[str]

    # allow copy paste or not
    get_cell_for_selection: Var[bool]

    on_paste: Var[bool]

    # Controls the drawing of the focus ring.
    draw_focus_ring: Var[bool]

    # Enables or disables the overlay shadow when scrolling horizontally.
    fixed_shadow_x: Var[bool]

    # Enables or disables the overlay shadow when scrolling vertically.
    fixed_shadow_y: Var[bool]

    # The number of columns which should remain in place when scrolling horizontally. Doesn't include rowMarkers.
    freeze_columns: Var[int]

    # Controls the header of the group header row.
    group_header_height: Var[int]

    # Controls the height of the header row.
    header_height: Var[int]

    # Additional header icons: (TODO: must be a map of name: svg)
    header_icons: Var[Any]

    # The maximum width a column can be automatically sized to.
    max_column_auto_width: Var[int]

    # The maximum width a column can be resized to.
    max_column_width: Var[int]

    # The minimum width a column can be resized to.
    min_column_width: Var[int]

    # Determins the height of each row.
    row_height: Var[int]

    # kind of raw marker (use Literal API ?)
    row_markers: Var[str]

    # Changes the starting index for row markers.
    row_marker_start_index: Var[int]

    # Sets the width of row markers in pixels, if unset row markers will automatically size.
    row_marker_width: Var[int]

    # enable horizontal smooth scrolling
    smooth_scroll_x: Var[bool]

    # enable vertical smooth scrolling
    smooth_scroll_y: Var[bool]

    # Controls the drawing of the left hand vertical border of a column. If set to a boolean value it controls all borders.
    # TODO: need to support a mapping (dict[int, bool] for handling separate columns)
    vertical_border: Var[bool]

    column_select: Var[str]

    prevent_diagonal_scrolling: Var[bool]

    overscroll_x: Var[int]

    overscroll_y: Var[int]

    scroll_offset_x: Var[int]
    scroll_offset_y: Var[int]

    # global theme
    theme: Var[dict]

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

    def get_event_triggers(self) -> Dict[str, Callable]:
        """The event triggers of the component.

        Returns:
            The dict describing the event triggers.
        """

        def edit_sig(pos, data: dict[str, Any]):
            return [pos, data]

        return {
            "on_cell_activated": lambda pos: [pos],
            "on_cell_clicked": lambda pos: [pos],
            "on_cell_context_menu": lambda pos: [pos],
            "on_cell_edited": edit_sig,
            "on_group_header_clicked": edit_sig,
            "on_group_header_context_menu": lambda grp_idx, data: [grp_idx, data],
            "on_group_header_renamed": lambda idx, val: [idx, val],
            "on_header_clicked": lambda pos: [pos],
            "on_header_context_menu": lambda pos: [pos],
            "on_header_menu_click": lambda col, pos: [col, pos],
            "on_item_hovered": lambda pos: [pos],
            "on_delete": lambda selection: [selection],
            "on_finished_editing": lambda new_value, movement: [new_value, movement],
            "on_row_appended": lambda: [],
            "on_selection_cleared": lambda: [],
        }

    def _get_hooks(self) -> str | None:
        editor_id = get_unique_variable_name()
        data_callback = f"getData_{editor_id}"
        self.get_cell_content = Var.create(data_callback, _var_is_local=False)  # type: ignore

        code = [f"function {data_callback}([col, row])" "{"]

        code.extend(
            [
                f"  if (row < {self.data._var_full_name}.length && col < {self.columns._var_full_name}.length)"
                " {",
                f"    const column = getDEColumn({self.columns._var_full_name}, col);",
                f"    const rowData = getDERow({self.data._var_full_name}, row);",
                f"    const cellData = locateCell(rowData, column);",
                "    return formatCell(cellData, column);",
                "  }",
                "  return { kind: GridCellKind.Loading};",
            ]
        )

        code.append("}")

        return "\n".join(code)

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
                5  # BaseVar.create(value=f"{data}.length()", is_local=False)
                if isinstance(data, Var)
                else len(data)
            )

        if not isinstance(columns, Var) and len(columns):
            if (
                types.is_dataframe(type(data))
                or isinstance(data, Var)
                and types.is_dataframe(data._var_type)
            ):
                raise ValueError(
                    "Cannot pass in both a pandas dataframe and columns to the data_editor component."
                )
            else:
                props["columns"] = [
                    format.format_data_editor_column(col) for col in columns
                ]
        else:
            ...

        if isinstance(data, Var):
            # ic(data.type_)
            ...

        props.setdefault("getCellForSelection", True)
        props.setdefault("onPaste", False)

        if props.pop("getCellContent", None) is not None:
            console.warn(
                "getCellContent is not user configurable, the provided value will be discarded"
            )
        grid = super().create(*children, **props)
        return Fragment.create(grid, Div.create(id="portal"))

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
