```python exec
import reflex as rx
from docs.datatable_tutorial.datatable_tutorial_utils import DataTableState, DataTableState2
from pcweb.pages.docs import library
```

# Data Table (Editable) Tutorial

```md alert info
#There is another [datatable component]({library.datadisplay.datatable.path}), which is only used for displaying data and does not support user interactivity or editing.
```

```python eval
rx.box(height="2em")
```

We need to start by defining our columns that describe the shape of our data. The column var should be typed as a `list` of `dict` (`list[dict]`), where each item describes the attributes of a single column in the table.

Each column dict recognizes the keys below:

1. `title`: The text to display in the header of the column
2. `id`: An id for the column, if not defined, will default to a lower case of title
3. `width`: The width of the column (in pixels)
4. `type`: The type of the columns, default to "str"

Below we define `DataTableState` with columns definitions in the `cols` var, and data about Harry Potter characters in the `data` var..

```python
class DataTableState(rx.State):
    """The app state."""
    cols: list[dict] = [
        {\"title": "Title", "type": "str"},
        {
            "title": "Name",
            "type": "str",
            "width": 300,
        },
        {
            "title": "Birth",
            "type": "str",
            "width": 150,
        },
        {
            "title": "Human",
            "type": "bool",
            "width": 80,
        },
        {
            "title": "House",
            "type": "str",
        },
        {
            "title": "Wand",
            "type": "str",
            "width": 250,
        },
        {
            "title": "Patronus",
            "type": "str",
        },
        {
            "title": "Blood status",
            "type": "str",
            "width": 200,
        },
    ]
    data = [
        ["1", "Harry James Potter", "31 July 1980", True, "Gryffindor", "11'  Holly  phoenix feather", "Stag", "Half-blood"],
        ["2", "Ronald Bilius Weasley", "1 March 1980", True,"Gryffindor", "12' Ash unicorn tail hair", "Jack Russell terrier", "Pure-blood"],
        ["3", "Hermione Jean Granger", "19 September, 1979", True, "Gryffindor", "10¾'  vine wood dragon heartstring", "Otter", "Muggle-born"], 
        ["4", "Albus Percival Wulfric Brian Dumbledore", "Late August 1881", True, "Gryffindor", "15' Elder Thestral tail hair core", "Phoenix", "Half-blood"], 
        ["5", "Rubeus Hagrid", "6 December 1928", False, "Gryffindor", "16'  Oak unknown core", "None", "Part-Human (Half-giant)"], 
        ["6", "Fred Weasley", "1 April, 1978", True, "Gryffindor", "Unknown", "Unknown", "Pure-blood"], 
        ["7", "George Weasley", "1 April, 1978", True, "Gryffindor", "Unknown", "Unknown", "Pure-blood"],
    ]
```

We then define a basic table by passing the previously defined state vars as props `columns` and `data` to the `rx.data_editor()` component,

```python demo
rx.data_editor(
    columns=DataTableState.cols,
    data=DataTableState.data,
)
```

This is enough to display the data, but there is no way to interact with it. On the next page we will explore how to add interactivity to our datatable.
