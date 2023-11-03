"""Data Editor component from glide-data-grid."""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from pandas import DataFrame

from reflex.base import Base
from reflex.components.component import Component, NoSSRComponent
from reflex.components.literals import LiteralRowMarker
from reflex.components.tags.tag import Tag
from reflex.utils import console, format, imports, types
from reflex.utils.serializers import serialize, serializer
from reflex.vars import BaseVar, ComputedVar, ImportVar, Var, get_unique_variable_name


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


class DataEditorTheme(Base):
    """The theme for the DataEditor component."""

    accent_color: Optional[str] = None
    accent_fg: Optional[str] = None
    accent_light: Optional[str] = None
    base_font_style: Optional[str] = None
    bg_bubble: Optional[str] = None
    bg_bubble_selected: Optional[str] = None
    bg_cell: Optional[str] = None
    bg_cell_medium: Optional[str] = None
    bg_header: Optional[str] = None
    bg_header_has_focus: Optional[str] = None
    bg_header_hovered: Optional[str] = None
    bg_icon_header: Optional[str] = None
    bg_search_result: Optional[str] = None
    border_color: Optional[str] = None
    cell_horizontal_padding: Optional[int] = None
    cell_vertical_padding: Optional[int] = None
    drilldown_border: Optional[str] = None
    editor_font_size: Optional[str] = None
    fg_icon_header: Optional[str] = None
    font_family: Optional[str] = None
    header_bottom_border_color: Optional[str] = None
    header_font_style: Optional[str] = None
    horizontal_border_color: Optional[str] = None
    line_height: Optional[int] = None
    link_color: Optional[str] = None
    text_bubble: Optional[str] = None
    text_dark: Optional[str] = None
    text_group_header: Optional[str] = None
    text_header: Optional[str] = None
    text_header_selected: Optional[str] = None
    text_light: Optional[str] = None
    text_medium: Optional[str] = None


class DataEditor(NoSSRComponent):
    """The DataEditor Component."""

    tag = "DataEditor"
    is_default = True
    library: str = "@glideapps/glide-data-grid@^5.3.0"
    lib_dependencies: List[str] = ["lodash", "marked", "react-responsive-carousel"]

    # Number of rows.
    rows: Var[int]

    # Headers of the columns for the data grid.
    columns: Var[Union[List[Dict[str, Any]], DataFrame]]

    # The data.
    data: Var[Union[List[List[Any]], List[Dict[str, Any]], DataFrame]]

    # The name of the callback used to find the data to display.
    get_cell_content: Var[str]

    # Allow selection for copying.
    get_cell_for_selection: Var[bool]

    # Allow paste.
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

    # Additional header icons:
    # header_icons: Var[Any] # (TODO: must be a map of name: svg)

    # The maximum width a column can be automatically sized to.
    max_column_auto_width: Var[int]

    # The maximum width a column can be resized to.
    max_column_width: Var[int]

    # The minimum width a column can be resized to.
    min_column_width: Var[int]

    # Determins the height of each row.
    row_height: Var[int]

    # Kind of row markers.
    row_markers: Var[LiteralRowMarker]

    # Changes the starting index for row markers.
    row_marker_start_index: Var[int]

    # Sets the width of row markers in pixels, if unset row markers will automatically size.
    row_marker_width: Var[int]

    # Enable horizontal smooth scrolling.
    smooth_scroll_x: Var[bool]

    # Enable vertical smooth scrolling.
    smooth_scroll_y: Var[bool]

    # Controls the drawing of the left hand vertical border of a column. If set to a boolean value it controls all borders.
    vertical_border: Var[bool]  # TODO: support a mapping (dict[int, bool])

    # Allow columns selections. ("none", "single", "multiple")
    column_select: Var[str]

    # Prevent diagonal scrolling.
    prevent_diagonal_scrolling: Var[bool]

    # Allow to scroll past the limit of the actual content on the horizontal axis.
    overscroll_x: Var[int]

    # Allow to scroll past the limit of the actual content on the vertical axis.
    overscroll_y: Var[int]

    # Initial scroll offset on the horizontal axis.
    scroll_offset_x: Var[int]

    # Initial scroll offset on the vertical axis.
    scroll_offset_y: Var[int]

    # global theme
    theme: Var[Union[DataEditorTheme, Dict]]

    # internal_value
    _editor_id: str = ""

    def _get_imports(self):
        return imports.merge_imports(
            super()._get_imports(),
            {
                "": {
                    ImportVar(
                        tag=f"{format.format_library_name(self.library)}/dist/index.css"
                    )
                },
                self.library: {ImportVar(tag="GridCellKind")},
                "/utils/helpers/dataeditor.js": {
                    ImportVar(
                        tag=f"formatDataEditorCells", is_default=False, install=False
                    ),
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
            "on_column_resize": lambda col, width: [col, width],
        }

    def _get_hooks(self) -> str | None:
        # Define the name of the getData callback associated with this component and assign to get_cell_content.
        data_callback = f"getData_{self._editor_id}"
        self.get_cell_content = Var.create(data_callback, _var_is_local=False)  # type: ignore

        code = [f"function {data_callback}([col, row])" "{"]

        if issubclass(self.data._var_type, DataFrame):
            columns_path = f"{self.data._var_full_name}.columns"
            data_path = f"{self.data._var_full_name}.data"
        else:
            columns_path = f"{self.columns._var_full_name}"
            data_path = f"{self.data._var_full_name}"

        code.extend(
            [
                f"    return formatDataEditorCells(col, row, {columns_path}, {data_path});",
                "  }",
            ]
        )

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

        columns = props.get("columns", None)
        data = props.get("data", [])
        rows = props.get("rows", None)

        # check ComputerVar return type annotation for data and columns props.
        if isinstance(data, ComputedVar) and data._var_type == Any:
            raise ValueError(
                f"Return type annotation for the computed var {data._var_full_name} should be provided."
            )

        if (
            columns is not None
            and isinstance(columns, ComputedVar)
            and columns._var_type == Any
        ):
            raise ValueError(
                f"Return type annotation for the computed var {columns._var_full_name} should be provided."
            )

        if types.is_dataframe(type(columns)) or (
            isinstance(columns, Var) and types.is_dataframe(columns._var_type)
        ):
            raise ValueError("DataFrame should be passed to the `data` props instead.")

        if types.is_dataframe(type(data)) or (
            isinstance(data, Var) and types.is_dataframe(data._var_type)
        ):
            if columns is not None:
                raise ValueError(
                    "Cannot pass in both a pandas dataframe and columns to the data_table component."
                )
            else:
                props["columns"] = data

        # If rows is not provided, determine from data.
        if rows is None:
            props["rows"] = data.length() if isinstance(data, Var) else len(data)

        if isinstance(columns, List):
            props["columns"] = [
                format.format_data_editor_column(col) for col in columns
            ]

        if "theme" in props:
            theme = props.get("theme")
            if isinstance(theme, Dict):
                props["theme"] = DataEditorTheme(**theme)

        # Allow by default to select a region of cells in the grid.
        props.setdefault("get_cell_for_selection", True)

        # Disable on_paste by default if not provided.
        props.setdefault("on_paste", False)

        if props.pop("get_cell_content", None) is not None:
            console.warn(
                "get_cell_content is not user configurable, the provided value will be discarded"
            )
        editor = super().create(*children, **props)

        # Define the id of the component in case multiple are used in the same page.
        editor._editor_id = get_unique_variable_name()
        return Div.create(
            editor,
            width=props.pop("width", "100%"),
            height=props.pop("height", "100%"),
        )

    def _render(self) -> Tag:
        if isinstance(self.data, Var) and types.is_dataframe(self.data._var_type):
            self.columns = BaseVar(
                _var_name=f"{self.data._var_name}.columns",
                _var_type=List[Any],
                _var_state=self.data._var_state,
            )
            self.data = BaseVar(
                _var_name=f"{self.data._var_name}.data",
                _var_type=List[List[Any]],
                _var_state=self.data._var_state,
            )
        if types.is_dataframe(type(self.data)):
            # If given a pandas df break up the data and columns
            data = serialize(self.data)
            assert isinstance(data, dict), "Serialized dataframe should be a dict."
            self.columns = Var.create_safe(data["columns"])
            self.data = Var.create_safe(data["data"])

        # Render the table.
        return super()._render()

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        """Get the app wrap components for the component.

        Returns:
            The app wrap components.
        """
        from reflex.el.elements import Div

        class Portal(Div):
            def get_ref(self):
                return None

        return {(-1, "DataEditorPortal"): Portal.create(id="portal")}


def format_dataframe_columns(df: DataFrame) -> List[Dict[str, str]]:
    """Format dataframe columns to a list of dicts.

    Args:
        df: The dataframe to format.

    Returns:
        The dataframe columns as a list of dicts.
    """
    formatted_columns = [
        format.format_data_editor_column({"title": column_, "type": str(type_)})
        for column_, type_ in df.dtypes.items()
    ]
    return formatted_columns


def format_dataframe_values(df: DataFrame) -> list[list[Any]]:
    """Format dataframe values to a list of lists.

    Args:
        df: The dataframe to format.

    Returns:
        The dataframe as a list of lists.
    """
    return [
        [str(d) if isinstance(d, (list, tuple)) else d for d in data]
        for data in list(df.values.tolist())
    ]


@serializer(override=True)
def serialize_dataframe(df: DataFrame) -> dict:
    """Serialize a pandas dataframe.

    Args:
        df: The dataframe to serialize.

    Returns:
        The serialized dataframe.
    """
    return {
        "columns": format_dataframe_columns(df),
        "data": format_dataframe_values(df),
    }


@serializer
def serialize_dataeditortheme(theme: DataEditorTheme):
    """The serializer for the data editor theme.

    Args:
        theme: The theme to serialize.

    Returns:
        The serialized theme.
    """
    return format.json_dumps(
        {format.to_camel_case(k): v for k, v in theme.__dict__.items() if v is not None}
    )
