```python exec
import reflex as rx
from docs.datatable_tutorial.datatable_tutorial_utils import DataTableState, DataTableState2
```

# Adding Interactivity to our DataTable

Now we will add interactivity to our datatable. We do this using event handlers and event triggers.

The first example implements a handler for the `on_cell_clicked` event trigger, which is called when the user clicks on a cell of the data editor. The event trigger receives the coordinates of the cell.

```python
class DataTableState(rx.State):
    clicked_cell: str = "Cell clicked: "

    ...


    def get_clicked_data(self, pos: tuple[int, int]) -> str:
        self.clicked_cell = f"Cell clicked: \{pos}"
        
```

The state has a var called `clicked_cell` that will store a message about which cell was clicked. We define an event handler `get_clicked_data` that updates the value of the `clicked_cell` var when it is called. In essence, we have clicked on a cell, called the `on_cell_clicked` event trigger which calls the `get_clicked_data` event handler, which updates the `clicked_cell` var.

```python demo
rx.text(DataTableState.clicked_cell)
```

```python demo
rx.data_editor(
    columns=DataTableState.cols,
    data=DataTableState.data,
    on_cell_clicked=DataTableState.get_clicked_data,
)
```

The event handler `on_cell_context_menu` can be used in the same way as `on_cell_clicked`, except here the event trigger is called when the user right clicks, i.e. when the cell should show a context menu.

## Editing cells

Another important type of interactivity we will showcase is how to edit cells. Here we use the `on_cell_edited` event trigger to update the data based on what the user entered.

```python
class DataTableState(rx.State):
    clicked_cell: str = "Cell clicked: "
    edited_cell: str = "Cell edited: "

    ...


    def get_clicked_data(self, pos) -> str:
        self.clicked_cell = f"Cell clicked: \{pos}"

    def get_edited_data(self, pos, val) -> str:
        col, row = pos
        self.data[row][col] = val["data"]
        self.edited_cell = f"Cell edited: \{pos}, Cell value: \{val["data"]}"
        
```

The `on_cell_edited` event trigger is called when the user modifies the content of a cell. It receives the coordinates of the cell and the modified content. We pass these into the `get_edited_data` event handler and use them to update the `data` state var at the appropriate position. We then update the `edited_cell` var value.

```python demo
rx.text(DataTableState.edited_cell)
```

```python demo
rx.data_editor(
    columns=DataTableState.cols,
    data=DataTableState.data,
    on_cell_clicked=DataTableState.get_clicked_data,
    on_cell_edited=DataTableState.get_edited_data,
)
```

## Group Header

We can define group headers which are headers that encompass a group of columns. We define these in the `columns` using the `group` property such as `"group": "Data"`. The `columns` would now be defined as below. Only the `Title` does not fall under a group header, all the rest fall under the `Data` group header.

```python
class DataTableState2(rx.State):
    """The app state."""

    ...

    cols: list[dict] = [
        {\"title": "Title", "type": "str"},
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
        },
    ]

    ...
```

The table now has a header as below.

```python demo
rx.data_editor(
    columns=DataTableState2.cols,
    data=DataTableState2.data,
    on_cell_clicked=DataTableState2.get_clicked_data,
    on_cell_edited=DataTableState2.get_edited_data,
)
```

There are several event triggers we can apply to the group header.

```python
class DataTableState2(rx.State):
    """The app state."""

    right_clicked_group_header : str = "Group header right clicked: "

    ...

    def get_group_header_right_click(self, index, val):
        self.right_clicked_group_header = f"Group header right clicked at index: \{index}, Group header value: \{val['group']}"

```

```python demo
rx.text(DataTableState2.right_clicked_group_header)
```

```python demo
rx.data_editor(
    columns=DataTableState2.cols,
    data=DataTableState2.data,
    on_cell_clicked=DataTableState2.get_clicked_data,
    on_cell_edited=DataTableState2.get_edited_data,
    on_group_header_context_menu=DataTableState2.get_group_header_right_click,
)
```

In this example we use the `on_group_header_context_menu` event trigger which is called when the user right-clicks on a group header. It returns the `index` and the `data` of the group header. We can also use the `on_group_header_clicked` and `on_group_header_renamed` event triggers which are called when the user left-clicks on a group header and when a user renames a group header respectively.

## More Event Triggers

There are several other event triggers that are worth exploring. The `on_item_hovered` event trigger is called whenever the user hovers over an item in the datatable. The `on_delete` event trigger is called when the user deletes a cell from the datatable.

The final event trigger to check out is `on_column_resize`. `on_column_resize` allows us to respond to the user dragging the handle between columns. The event trigger returns the `col` we are adjusting and the new `width` we have defined. The `col` that is returned is a dictionary for example: `\{'title': 'Name', 'type': 'str', 'group': 'Data', 'width': 198, 'pos': 1}`. We then index into `self.cols` defined in our state and change the `width` of that column using this code: `self.cols[col['pos']]['width'] = width`.

```python
class DataTableState2(rx.State):
    """The app state."""

    ...

    item_hovered: str = "Item Hovered: "
    deleted: str = "Deleted: "

    ...


    def get_item_hovered(self, pos) -> str:
        self.item_hovered = f"Item Hovered type: \{pos['kind']}, Location: \{pos['location']}"
        
    def get_deleted_item(self, selection):
        self.deleted = f"Deleted cell: \{selection['current']['cell']}"

    def column_resize(self, col, width):
        self.cols[col['pos']]['width'] = width 
```

```python demo
rx.text(DataTableState2.item_hovered)
```

```python demo
rx.text(DataTableState2.deleted)
```

```python demo
rx.data_editor(
    columns=DataTableState2.cols,
    data=DataTableState2.data,
    on_cell_clicked=DataTableState2.get_clicked_data,
    on_cell_edited=DataTableState2.get_edited_data,
    on_group_header_context_menu=DataTableState2.get_group_header_right_click,
    on_item_hovered=DataTableState2.get_item_hovered,
    on_delete=DataTableState2.get_deleted_item,
    on_column_resize=DataTableState2.column_resize,
)
```
