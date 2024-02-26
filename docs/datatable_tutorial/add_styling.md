```python exec
import reflex as rx
from docs.datatable_tutorial.datatable_tutorial_utils import DataTableState, DataTableState2
from pcweb.pages.docs import library
```

# DataTable Styling

There are props that we can explore to ensure the datatable is shaped correctly and reacts in the way we expect. We can set `on_paste` to `True`, which allows us to paste directly into a cell. We can use `draw_focus_ring` to draw a ring around the cells when selected, this defaults to `True` so can be turned off if we do not want it. The `rows` prop can be used to hard code the number of rows that we show.

`freeze_columns` is used to keep a certain number of the left hand columns frozen when scrolling horizontally. `group_header_height` and `header_height` define the height of the group header and the individual headers respectively. `max_column_width` and `min_column_width` define how large or small the columns are allowed to be with the manual column resizing. We can also define the `row_height` to make the rows more nicely spaced.

We can add `row_markers`, which appear on the furthest left side of the table. They can take values of `'none', 'number', 'checkbox', 'both', 'clickable-number'`. We can set `smooth_scroll_x` and `smooth_scroll_y`, which allows us to smoothly scroll along the columns and rows.

By default there is a `vertical_border` between the columns, we can turn it off by setting this prop to `False`. We can define how many columns a user can select at a time by setting the `column_select` prop. It can take values of `"none", "single", "multi"`.

We can allow `overscroll_x`, which allows users to scroll past the limit of the actual horizontal content. There is an equivalent `overscroll_y`.

Check out [these docs]({library.datadisplay.data_editor.path}) for more information on these props.

```python demo
rx.data_editor(
    columns=DataTableState2.cols,
    data=DataTableState2.data,

    #rows=4,
    on_paste=True,
    draw_focus_ring=False,
    freeze_columns=2,
    group_header_height=50,
    header_height=60,
    max_column_width=300,
    min_column_width=100,
    row_height=50,
    row_markers='clickable-number',
    smooth_scroll_x=True,
    vertical_border=False,
    column_select="multi",
    overscroll_x=100,


    on_cell_clicked=DataTableState2.get_clicked_data,
    on_cell_edited=DataTableState2.get_edited_data,
    on_group_header_context_menu=DataTableState2.get_group_header_right_click,
    on_item_hovered=DataTableState2.get_item_hovered,
    on_delete=DataTableState2.get_deleted_item,
    on_column_resize=DataTableState2.column_resize,
)
```

## Theming

Lastly there is a `theme` prop that allows us to pass in all color and font information for the data table.

```python
darkTheme = {
    "accentColor": "#8c96ff",
    "accentLight": "rgba(202, 206, 255, 0.253)",
    "textDark": "#ffffff",
    "textMedium": "#b8b8b8",
    "textLight": "#a0a0a0",
    "textBubble": "#ffffff",
    "bgIconHeader": "#b8b8b8",
    "fgIconHeader": "#000000",
    "textHeader": "#a1a1a1",
    "textHeaderSelected": "#000000",
    "bgCell": "#16161b",
    "bgCellMedium": "#202027",
    "bgHeader": "#212121",
    "bgHeaderHasFocus": "#474747",
    "bgHeaderHovered": "#404040",
    "bgBubble": "#212121",
    "bgBubbleSelected": "#000000",
    "bgSearchResult": "#423c24",
    "borderColor": "rgba(225,225,225,0.2)",
    "drilldownBorder": "rgba(225,225,225,0.4)",
    "linkColor": "#4F5DFF",
    "headerFontStyle": "bold 14px",
    "baseFontStyle": "13px",
    "fontFamily": "Inter, Roboto, -apple-system, BlinkMacSystemFont, avenir next, avenir, segoe ui, helvetica neue, helvetica, Ubuntu, noto, arial, sans-serif",
}
```

```python exec
darkTheme = {
    "accentColor": "#8c96ff",
    "accentLight": "rgba(202, 206, 255, 0.253)",
    "textDark": "#ffffff",
    "textMedium": "#b8b8b8",
    "textLight": "#a0a0a0",
    "textBubble": "#ffffff",
    "bgIconHeader": "#b8b8b8",
    "fgIconHeader": "#000000",
    "textHeader": "#a1a1a1",
    "textHeaderSelected": "#000000",
    "bgCell": "#16161b",
    "bgCellMedium": "#202027",
    "bgHeader": "#212121",
    "bgHeaderHasFocus": "#474747",
    "bgHeaderHovered": "#404040",
    "bgBubble": "#212121",
    "bgBubbleSelected": "#000000",
    "bgSearchResult": "#423c24",
    "borderColor": "rgba(225,225,225,0.2)",
    "drilldownBorder": "rgba(225,225,225,0.4)",
    "linkColor": "#4F5DFF",
    "headerFontStyle": "bold 14px",
    "baseFontStyle": "13px",
    "fontFamily": "Inter, Roboto, -apple-system, BlinkMacSystemFont, avenir next, avenir, segoe ui, helvetica neue, helvetica, Ubuntu, noto, arial, sans-serif",
}
```

```python demo
rx.data_editor(
    columns=DataTableState2.cols,
    data=DataTableState2.data,

    on_paste=True,
    draw_focus_ring=False,
    freeze_columns=2,
    group_header_height=50,
    header_height=60,
    max_column_width=300,
    min_column_width=100,
    row_height=50,
    row_markers='clickable-number',
    smooth_scroll_x=True,
    vertical_border=False,
    column_select="multi",
    overscroll_x=100,
    theme=darkTheme,


    on_cell_clicked=DataTableState2.get_clicked_data,
    on_cell_edited=DataTableState2.get_edited_data,
    on_group_header_context_menu=DataTableState2.get_group_header_right_click,
    on_item_hovered=DataTableState2.get_item_hovered,
    on_delete=DataTableState2.get_deleted_item,
    on_column_resize=DataTableState2.column_resize,
)
```
