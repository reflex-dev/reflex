---
components:
    - rx.data_editor
---

# Data Editor

A datagrid editor based on [Glide Data Grid](https://grid.glideapps.com/)

```python exec
import reflex as rx
from pcweb.pages.docs import library
from typing import Any

columns: list[dict[str, str]] = [
    {
        "title":"Code",
        "type": "str",
    },
    {
        "title":"Value",
        "type": "int",
    }, 
    {
        "title":"Activated",
        "type": "bool",
    },
]
data: list[list[Any]] = [
    ["A", 1, True],
    ["B", 2, False],
    ["C", 3, False],
    ["D", 4, True],
    ["E", 5, True],
    ["F", 6, False],
]

```

This component is introduced as an alternative to the [datatable]({library.tables_and_data_grids.data_table.path}) to support editing the displayed data.

## Columns

The columns definition should be a `list` of `dict`, each `dict` describing the associated columns.
Property of a column dict:

- `title`: The text to display in the header of the column.
- `id`: An id for the column, if not defined, will default to a lower case of `title`
- `width`: The width of the column.
- `type`: The type of the columns, default to `"str"`.

## Data

The `data` props of `rx.data_editor` accept a `list` of `list`, where each `list` represent a row of data to display in the table.

## Simple Example

Here is a basic example of using the data_editor representing data with no interaction and no styling. Below we define the `columns` and the `data` which are taken in by the `rx.data_editor` component. When we define the `columns` we must define a `title` and a `type` for each column we create. The columns in the `data` must then match the defined `type` or errors will be thrown.

```python demo box
rx.data_editor(
    columns=columns,
    data=data,
)
```

```python
columns: list[dict[str, str]] = [
    {
        "title":"Code",
        "type": "str",
    },
    {
        "title":"Value",
        "type": "int",
    }, 
    {
        "title":"Activated",
        "type": "bool",
    },
]
data: list[list[Any]] = [
    ["A", 1, True],
    ["B", 2, False],
    ["C", 3, False],
    ["D", 4, True],
    ["E", 5, True],
    ["F", 6, False],
]
```

```python
rx.data_editor(
    columns=columns,
    data=data,
)
```

## Interactive Example

```python exec
class DataEditorState_HP(rx.State):

    clicked_data: str = "Cell clicked: "
    cols: list[Any] = [
        {"title": "Title", "type": "str"},
        {
            "title": "Name",
            "type": "str",
            "group": "Data",
            "width": 300,
        },
        {
            "title": "Birth",
            "type": "str",
            "id": "date",
            "group": "Data",
            "width": 150,
        },
        {
            "title": "Human",
            "type": "bool",
            "group": "Data",
            "width": 80,
        },
        {
            "title": "House",
            "type": "str",
            "id": "date",
            "group": "Data",
        },
        {
            "title": "Wand",
            "type": "str",
            "id": "date",
            "group": "Data",
            "width": 250,
        },
        {
            "title": "Patronus",
            "type": "str",
            "id": "date",
            "group": "Data",
        },
        {
            "title": "Blood status",
            "type": "str",
            "id": "date",
            "group": "Data",
            "width": 200,
        }
    ]

    data = [
        ["1", "Harry James Potter", "31 July 1980", True, "Gryffindor", "11'  Holly  phoenix feather", "Stag", "Half-blood"],
        ["2", "Ronald Bilius Weasley", "1 March 1980", True,"Gryffindor", "12' Ash unicorn tail hair", "Jack Russell terrier", "Pure-blood"],
        ["3", "Hermione Jean Granger", "19 September, 1979", True, "Gryffindor", "10¾'  vine wood dragon heartstring", "Otter", "Muggle-born"], 
        ["4", "Albus Percival Wulfric Brian Dumbledore", "Late August 1881", True, "Gryffindor", "15' Elder Thestral tail hair core", "Phoenix", "Half-blood"], 
        ["5", "Rubeus Hagrid", "6 December 1928", False, "Gryffindor", "16'  Oak unknown core", "None", "Part-Human (Half-giant)"], 
        ["6", "Fred Weasley", "1 April, 1978", True, "Gryffindor", "Unknown", "Unknown", "Pure-blood"], 
    ]

    def click_cell(self, pos):
        col, row = pos
        yield self.get_clicked_data(pos)
        

    def get_clicked_data(self, pos) -> str:
        self.clicked_data = f"Cell clicked: {pos}"
        
```

Here we define a State, as shown below, that allows us to print the location of the cell as a heading when we click on it, using the `on_cell_clicked` `event trigger`. Check out all the other `event triggers` that you can use with datatable at the bottom of this page. We also define a `group` with a label `Data`. This groups all the columns with this `group` label under a larger group `Data` as seen in the table below.

```python demo box
rx.heading(DataEditorState_HP.clicked_data)
```

```python demo box
rx.data_editor(
    columns=DataEditorState_HP.cols,
    data=DataEditorState_HP.data,
    on_cell_clicked=DataEditorState_HP.click_cell,
)
```

```python
class DataEditorState_HP(rx.State):
    
    clicked_data: str = "Cell clicked: "

    cols: list[Any] = [
        {
            "title": "Title", 
            "type": "str"
        },
        {
            "title": "Name",
            "type": "str",
            "group": "Data",
            "width": 300,
        },
        {
            "title": "Birth",
            "type": "str",
            "group": "Data",
            "width": 150,
        },
        {
            "title": "Human",
            "type": "bool",
            "group": "Data",
            "width": 80,
        },
        {
            "title": "House",
            "type": "str",
            "group": "Data",
        },
        {
            "title": "Wand",
            "type": "str",
            "group": "Data",
            "width": 250,
        },
        {
            "title": "Patronus",
            "type": "str",
            "group": "Data",
        },
        {
            "title": "Blood status",
            "type": "str",
            "group": "Data",
            "width": 200,
        }
    ]

    data = [
        ["1", "Harry James Potter", "31 July 1980", True, "Gryffindor", "11'  Holly  phoenix feather", "Stag", "Half-blood"],
        ["2", "Ronald Bilius Weasley", "1 March 1980", True,"Gryffindor", "12' Ash unicorn tail hair", "Jack Russell terrier", "Pure-blood"],
        ["3", "Hermione Jean Granger", "19 September, 1979", True, "Gryffindor", "10¾'  vine wood dragon heartstring", "Otter", "Muggle-born"], 
        ["4", "Albus Percival Wulfric Brian Dumbledore", "Late August 1881", True, "Gryffindor", "15' Elder Thestral tail hair core", "Phoenix", "Half-blood"], 
        ["5", "Rubeus Hagrid", "6 December 1928", False, "Gryffindor", "16'  Oak unknown core", "None", "Part-Human (Half-giant)"], 
        ["6", "Fred Weasley", "1 April, 1978", True, "Gryffindor", "Unknown", "Unknown", "Pure-blood"], 
    ]


    def click_cell(self, pos):
        col, row = pos
        yield self.get_clicked_data(pos)
        

    def get_clicked_data(self, pos) -> str:
        self.clicked_data = f"Cell clicked: \{pos}"
```

```python
rx.data_editor(
    columns=DataEditorState_HP.cols,
    data=DataEditorState_HP.data,
    on_cell_clicked=DataEditorState_HP.click_cell,
)
```

## Styling Example

Now let's style our datatable to make it look more aesthetic and easier to use. We must first import `DataEditorTheme` and then we can start setting our style props as seen below in `dark_theme`.

We then set these themes using `theme=DataEditorTheme(**dark_theme)`. On top of the styling we can also set some `props` to make some other aesthetic changes to our datatable. We have set the `row_height` to equal `50` so that the content is easier to read. We have also made the `smooth_scroll_x` and `smooth_scroll_y` equal `True` so that we can smoothly scroll along the columns and rows. Finally, we added `column_select=single`, where column select can take any of the following values `none`, `single` or `multiple`.

```python exec
from reflex.components.datadisplay.dataeditor import DataEditorTheme
dark_theme = {
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

```python demo box
rx.data_editor(
    columns=DataEditorState_HP.cols,
    data=DataEditorState_HP.data,
    row_height=80,
    smooth_scroll_x=True,
    smooth_scroll_y=True,
    column_select="single",
    theme=DataEditorTheme(**dark_theme),
    height="30vh",
)
```

```python
from reflex.components.datadisplay.dataeditor import DataEditorTheme
dark_theme_snake_case = {
    "accent_color": "#8c96ff",
    "accent_light": "rgba(202, 206, 255, 0.253)",
    "text_dark": "#ffffff",
    "text_medium": "#b8b8b8",
    "text_light": "#a0a0a0",
    "text_bubble": "#ffffff",
    "bg_icon_header": "#b8b8b8",
    "fg_icon_header": "#000000",
    "text_header": "#a1a1a1",
    "text_header_selected": "#000000",
    "bg_cell": "#16161b",
    "bg_cell_medium": "#202027",
    "bg_header": "#212121",
    "bg_header_has_focus": "#474747",
    "bg_header_hovered": "#404040",
    "bg_bubble": "#212121",
    "bg_bubble_selected": "#000000",
    "bg_search_result": "#423c24",
    "border_color": "rgba(225,225,225,0.2)",
    "drilldown_border": "rgba(225,225,225,0.4)",
    "link_color": "#4F5DFF",
    "header_font_style": "bold 14px",
    "base_font_style": "13px",
    "font_family": "Inter, Roboto, -apple-system, BlinkMacSystemFont, avenir next, avenir, segoe ui, helvetica neue, helvetica, Ubuntu, noto, arial, sans-serif",
}
```

```python
rx.data_editor(
    columns=DataEditorState_HP.cols,
    data=DataEditorState_HP.data,
    row_height=80,
    smooth_scroll_x=True,
    smooth_scroll_y=True,
    column_select="single",
    theme=DataEditorTheme(**dark_theme),
    height="30vh",
)
```
