"""Data Editor component from glide-data-grid."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Literal, TypedDict

from reflex_base.components.component import Component, NoSSRComponent, field
from reflex_base.components.literals import LiteralRowMarker
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.utils import console, format, types
from reflex_base.utils.imports import ImportDict, ImportVar
from reflex_base.utils.serializers import serializer
from reflex_base.vars import get_unique_variable_name
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.function import FunctionStringVar
from reflex_base.vars.sequence import ArrayVar


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


@dataclasses.dataclass
class DataEditorThemeBase:
    """The theme for the DataEditor component."""

    accent_color: str | None = None
    accent_fg: str | None = None
    accent_light: str | None = None
    base_font_style: str | None = None
    bg_bubble: str | None = None
    bg_bubble_selected: str | None = None
    bg_cell: str | None = None
    bg_cell_medium: str | None = None
    bg_header: str | None = None
    bg_header_has_focus: str | None = None
    bg_header_hovered: str | None = None
    bg_icon_header: str | None = None
    bg_search_result: str | None = None
    border_color: str | None = None
    cell_horizontal_padding: int | None = None
    cell_vertical_padding: int | None = None
    drilldown_border: str | None = None
    editor_font_size: str | None = None
    fg_icon_header: str | None = None
    font_family: str | None = None
    header_bottom_border_color: str | None = None
    header_font_style: str | None = None
    horizontal_border_color: str | None = None
    line_height: int | None = None
    link_color: str | None = None
    text_bubble: str | None = None
    text_dark: str | None = None
    text_group_header: str | None = None
    text_header: str | None = None
    text_header_selected: str | None = None
    text_light: str | None = None
    text_medium: str | None = None


@dataclasses.dataclass(init=False)
class DataEditorTheme(DataEditorThemeBase):
    """The theme for the DataEditor component."""

    def __init__(self, **kwargs: Any):
        """Initialize the DataEditorTheme.

        Args:
            **kwargs: The keyword arguments to initialize the theme.
        """
        kwargs = {format.to_snake_case(k): v for k, v in kwargs.items()}
        super().__init__(**kwargs)


class Bounds(TypedDict):
    """The bounds of the group header."""

    x: int
    y: int
    width: int
    height: int


class CompatSelection(TypedDict):
    """The selection."""

    items: list


class Rectangle(TypedDict):
    """The bounds of the group header."""

    x: int
    y: int
    width: int
    height: int


class GridSelectionCurrent(TypedDict):
    """The current selection."""

    cell: tuple[int, int]
    range: Rectangle
    rangeStack: list[Rectangle]


class GridSelection(TypedDict):
    """The grid selection."""

    current: GridSelectionCurrent | None
    columns: CompatSelection
    rows: CompatSelection


class GroupHeaderClickedEventArgs(TypedDict):
    """The arguments for the group header clicked event."""

    kind: str
    group: str
    location: tuple[int, int]
    bounds: Bounds
    isEdge: bool
    shiftKey: bool
    ctrlKey: bool
    metaKey: bool
    isTouch: bool
    localEventX: int
    localEventY: int
    button: int
    buttons: int
    scrollEdge: tuple[int, int]


class GridCell(TypedDict):
    """The grid cell."""

    span: list[int] | None


class GridColumn(TypedDict):
    """The grid column."""

    title: str
    group: str | None


class DataEditor(NoSSRComponent):
    """The DataEditor Component."""

    tag = "DataEditor"
    is_default = True
    library: str | None = "@glideapps/glide-data-grid@6.0.3"
    lib_dependencies: list[str] = [
        "lodash@4.18.1",
        "react-responsive-carousel@3.2.23",
    ]

    rows: Var[int] = field(doc="Number of rows.")

    columns: Var[Sequence[dict[str, Any]]] = field(
        doc="Headers of the columns for the data grid."
    )

    data: Var[Sequence[Sequence[Any]]] = field(doc="The data.")

    get_cell_content: Var[str] = field(
        doc="The name of the callback used to find the data to display."
    )

    get_cells_for_selection: Var[bool] = field(doc="Allow selection for copying.")

    on_paste: Var[bool] = field(doc="Allow paste.")

    draw_focus_ring: Var[bool] = field(doc="Controls the drawing of the focus ring.")

    fixed_shadow_x: Var[bool] = field(
        doc="Enables or disables the overlay shadow when scrolling horizontally."
    )

    fixed_shadow_y: Var[bool] = field(
        doc="Enables or disables the overlay shadow when scrolling vertically."
    )

    fill_handle: Var[bool] = field(doc="Controls the presence of the fill indicator")

    freeze_columns: Var[int] = field(
        doc="The number of columns which should remain in place when scrolling horizontally. Doesn't include rowMarkers."
    )

    group_header_height: Var[int] = field(
        doc="Controls the header of the group header row."
    )

    header_height: Var[int] = field(doc="Controls the height of the header row.")

    # Additional header icons:
    # header_icons: Var[Any] # (TODO: must be a map of name: svg) #noqa: ERA001

    max_column_auto_width: Var[int] = field(
        doc="The maximum width a column can be automatically sized to."
    )

    max_column_width: Var[int] = field(
        doc="The maximum width a column can be resized to."
    )

    min_column_width: Var[int] = field(
        doc="The minimum width a column can be resized to."
    )

    row_height: Var[int] = field(doc="Determines the height of each row.")

    row_markers: Var[LiteralRowMarker] = field(
        doc='Kind of row markers. Options are: "none", "number", "checkbox", "both", "checkbox-visible", "clickable-number".'
    )

    row_marker_start_index: Var[int] = field(
        doc="Changes the starting index for row markers."
    )

    row_marker_width: Var[int] = field(
        doc="Sets the width of row markers in pixels, if unset row markers will automatically size."
    )

    smooth_scroll_x: Var[bool] = field(doc="Enable horizontal smooth scrolling.")

    smooth_scroll_y: Var[bool] = field(doc="Enable vertical smooth scrolling.")

    vertical_border: Var[  # TODO: support a mapping (dict[int, bool])
        bool
    ] = field(
        doc="Controls the drawing of the left hand vertical border of a column. If set to a boolean value it controls all borders."
    )

    column_select: Var[Literal["none", "single", "multi"]] = field(
        doc='Allow columns selections. ("none", "single", "multi")'
    )

    range_select: Var[Literal["none", "cell", "rect", "multi-cell", "multi-rect"]] = (
        field(
            doc='Allow range selections. ("none", "cell", "rect", "multi-cell", "multi-rect").'
        )
    )

    row_select: Var[Literal["none", "single", "multi"]] = field(
        doc='Allow row selections. ("none", "single", "multi").'
    )

    prevent_diagonal_scrolling: Var[bool] = field(doc="Prevent diagonal scrolling.")

    overscroll_x: Var[int] = field(
        doc="Allow to scroll past the limit of the actual content on the horizontal axis."
    )

    overscroll_y: Var[int] = field(
        doc="Allow to scroll past the limit of the actual content on the vertical axis."
    )

    scroll_offset_x: Var[int] = field(
        doc="Initial scroll offset on the horizontal axis."
    )

    scroll_offset_y: Var[int] = field(doc="Initial scroll offset on the vertical axis.")

    range_selection_blending: Var[Literal["exclusive", "mixed"]] = field(
        doc='Controls which types of range selections can exist at the same time. ("exclusive", "mixed").'
    )

    column_selection_blending: Var[Literal["exclusive", "mixed"]] = field(
        doc='Controls which types of column selections can exist at the same time. ("exclusive", "mixed").'
    )

    row_selection_blending: Var[Literal["exclusive", "mixed"]] = field(
        doc='Controls which types of row selections can exist at the same time. ("exclusive", "mixed").'
    )

    row_selection_mode: Var[Literal["auto", "multi"]] = field(
        doc='Controls row marker selection behavior. "auto" adapts to touch/mouse, "multi" acts as if Ctrl is pressed. ("auto", "multi").'
    )

    span_range_behavior: Var[Literal["default", "allowPartial"]] = field(
        doc='Controls how spans are handled in selections. ("default", "allowPartial").'
    )

    theme: Var[DataEditorTheme | dict] = field(doc="global theme")

    on_cell_activated: EventHandler[passthrough_event_spec(tuple[int, int])] = field(
        doc="Fired when a cell is activated."
    )

    on_cell_clicked: EventHandler[passthrough_event_spec(tuple[int, int])] = field(
        doc="Fired when a cell is clicked."
    )

    on_cell_context_menu: EventHandler[passthrough_event_spec(tuple[int, int])] = field(
        doc="Fired when a cell is right-clicked."
    )

    on_cell_edited: EventHandler[passthrough_event_spec(tuple[int, int], GridCell)] = (
        field(doc="Fired when a cell is edited.")
    )

    on_group_header_clicked: EventHandler[
        passthrough_event_spec(tuple[int, int], GridCell)
    ] = field(doc="Fired when a group header is clicked.")

    on_group_header_context_menu: EventHandler[
        passthrough_event_spec(int, GroupHeaderClickedEventArgs)
    ] = field(doc="Fired when a group header is right-clicked.")

    on_group_header_renamed: EventHandler[passthrough_event_spec(str, str)] = field(
        doc="Fired when a group header is renamed."
    )

    on_header_clicked: EventHandler[passthrough_event_spec(tuple[int, int])] = field(
        doc="Fired when a header is clicked."
    )

    on_header_context_menu: EventHandler[passthrough_event_spec(tuple[int, int])] = (
        field(doc="Fired when a header is right-clicked.")
    )

    on_header_menu_click: EventHandler[passthrough_event_spec(int, Rectangle)] = field(
        doc="Fired when a header menu item is clicked."
    )

    on_item_hovered: EventHandler[passthrough_event_spec(tuple[int, int])] = field(
        doc="Fired when an item is hovered."
    )

    on_delete: EventHandler[passthrough_event_spec(GridSelection)] = field(
        doc="Fired when a selection is deleted."
    )

    on_finished_editing: EventHandler[
        passthrough_event_spec(GridCell | None, tuple[int, int])
    ] = field(doc="Fired when editing is finished.")

    on_row_appended: EventHandler[no_args_event_spec] = field(
        doc="Fired when a row is appended."
    )

    grid_selection: Var[GridSelection] = field(
        doc="The current grid selection state (columns, rows, and current cell/range). Must be used when on_grid_selection_change is used otherwise updates will not be reflected in the grid."
    )

    on_grid_selection_change: EventHandler[passthrough_event_spec(GridSelection)] = (
        field(
            doc="Fired when the grid selection changes. Will pass the current selection, the selected columns and the selected rows."
        )
    )

    on_selection_cleared: EventHandler[no_args_event_spec] = field(
        doc="Fired when the selection is cleared."
    )

    on_column_resize: EventHandler[passthrough_event_spec(GridColumn, int)] = field(
        doc="Fired when a column is resized."
    )

    show_search: Var[bool] = field(doc="Shows search bar.")

    on_search_close: EventHandler[no_args_event_spec] = field(
        doc="Fired when the search close button is clicked."
    )

    # Custom cell renderers
    custom_renderers: Var[Any]

    def add_imports(self) -> ImportDict:
        """Add imports for the component.

        Returns:
            The import dict.
        """
        if self.library is None:
            return {}
        return {
            "": f"{format.format_library_name(self.library)}/dist/index.css",
            self.library: ["GridCellKind", "CompactSelection"],
            "$/utils/helpers/dataeditor.js": ImportVar(
                tag="formatDataEditorCells", is_default=False, install=False
            ),
        }

    def add_custom_code(self) -> list[str]:
        """Add custom code for reconstructing GridSelection with CompactSelection objects.

        Note: When using on_grid_selection_change, Glide Data Grid will not update its internal selection state automatically. Instead,
        the grid_selection prop must be updated with a GridSelection object that has CompactSelection objects for the columns and rows properties.
        This function provides the necessary JavaScript code to reconstruct the GridSelection object from a dict representation.

        Returns:
            JavaScript code to reconstruct GridSelection.
        """
        return [
            """
        function reconstructGridSelection(selection) {
            if (!selection || typeof selection !== 'object') {
                return undefined;
            }

            const reconstructCompactSelection = (data) => {
                if (!data || !data.items || !Array.isArray(data.items)) {
                    return CompactSelection.empty();
                }

                const items = data.items;
                if (items.length === 0) {
                    return CompactSelection.empty();
                }

                let result = CompactSelection.empty();

                // Items are stored as [start, end) ranges in CompactSelection internal format
                for (const item of items) {
                    if (Array.isArray(item) && item.length === 2) {
                        const [start, end] = item;
                        result = result.add([start, end]);
                    }
                }

                return result;
            };

            return {
                current: selection.current || undefined,
                columns: reconstructCompactSelection(selection.columns),
                rows: reconstructCompactSelection(selection.rows)
            };
        }
                    """
        ]

    def add_hooks(self) -> list[str]:
        """Get the hooks to render.

        Returns:
            The hooks to render.
        """
        # Define the id of the component in case multiple are used in the same page.
        editor_id = get_unique_variable_name()

        # Define the name of the getData callback associated with this component and assign to get_cell_content.
        if self.get_cell_content is not None:
            data_callback = self.get_cell_content._js_expr
        else:
            data_callback = f"getData_{editor_id}"
            self.get_cell_content = Var(_js_expr=data_callback)

        code = [f"function {data_callback}([col, row]){{"]

        columns_path = str(self.columns)
        data_path = str(self.data)

        code.extend([
            f"    return formatDataEditorCells(col, row, {columns_path}, {data_path});",
            "  }",
        ])

        return ["\n".join(code)]

    @classmethod
    def create(cls, *children, extended_cell_types: bool = False, **props) -> Component:
        """Create the DataEditor component.

        Args:
            *children: The children of the data editor.
            extended_cell_types: Whether to enable extended cell types.
            **props: The props of the data editor.

        Returns:
            The DataEditor component.&

        Raises:
            ValueError: invalid input.
        """
        from reflex_components_core.el import Div

        columns = props.get("columns", [])
        data = props.get("data", [])
        rows = props.get("rows")

        # If rows is not provided, determine from data.
        if rows is None:
            if isinstance(data, Var) and not isinstance(data, ArrayVar):
                msg = "DataEditor data must be an ArrayVar if rows is not provided."
                raise ValueError(msg)

            props["rows"] = data.length() if isinstance(data, ArrayVar) else len(data)

        if not isinstance(columns, Var) and len(columns):
            if types.is_dataframe(type(data)) or (
                isinstance(data, Var) and types.is_dataframe(data._var_type)
            ):
                msg = "Cannot pass in both a pandas dataframe and columns to the data_editor component."
                raise ValueError(msg)
            props["columns"] = [
                format.format_data_editor_column(col) for col in columns
            ]

        if "theme" in props:
            theme = props.get("theme")
            if isinstance(theme, Mapping):
                props["theme"] = DataEditorTheme(**theme)

        # Allow by default to select a region of cells in the grid.
        props.setdefault("get_cells_for_selection", True)

        # Disable on_paste by default if not provided.
        props.setdefault("on_paste", False)

        if props.pop("get_cell_content", None) is not None:
            console.warn(
                "get_cell_content is not user configurable, the provided value will be discarded"
            )

        # Apply the reconstruction function to grid_selection if it's a Var
        if (grid_selection := props.get("grid_selection")) is not None and isinstance(
            grid_selection, Var
        ):
            props["grid_selection"] = FunctionStringVar.create(
                "reconstructGridSelection"
            ).call(grid_selection)

        if extended_cell_types:
            props["custom_renderers"] = Var(
                "allCells",
                _var_data=VarData(
                    imports={
                        "@glideapps/glide-data-grid-cells@6.0.3": ImportVar(
                            tag="allCells", is_default=False
                        )
                    }
                ),
            )

        grid = super().create(*children, **props)
        return Div.create(
            grid,
            width=props.pop("width", "100%"),
            height=props.pop("height", "100%"),
        )

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        """Get the app wrap components for the component.

        Returns:
            The app wrap components.
        """
        from reflex_components_core.el import Div

        class Portal(Div):
            def get_ref(self):
                return None

        return {
            (-1, "DataEditorPortal"): Portal.create(
                id="portal",
                position="fixed",
                top=0,
            )
        }


@serializer
def serialize_dataeditortheme(theme: DataEditorTheme):
    """The serializer for the data editor theme.

    Args:
        theme: The theme to serialize.

    Returns:
        The serialized theme.
    """
    return {
        format.to_camel_case(k): v for k, v in theme.__dict__.items() if v is not None
    }


data_editor = DataEditor.create
data_editor_theme = DataEditorTheme
