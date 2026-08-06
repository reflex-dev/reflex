---
components:
  - rx.data_table
meta_description: "Display data in an interactive table in Python with Reflex. The rx.data_table component turns a pandas DataFrame into a searchable, sortable, paginated data table — all in pure Python."
---

```python exec
import reflex as rx
```

# Data Table

Reflex's data table component (`rx.data_table`) is a great way to display static data — such as a pandas DataFrame — as an interactive table in pure Python.
You can pass a pandas dataframe to the data prop to create the table, with built-in search, sorting, and pagination.

In this example we will read data from a csv file, convert it to a pandas dataframe and display it in a data_table.

We will also add a search, pagination, sorting to the data_table to make it more accessible.

If you want to [add, edit or remove data](/docs/library/tables-and-data-grids/table) in your app or deal with anything but static data then the [`rx.table`](/docs/library/tables-and-data-grids/table) might be a better fit for your use case.

```python demo box
rx.data_table(
    data=[
        ["Avery Bradley", "6-2", 25.0],
        ["Jae Crowder", "6-6", 25.0],
        ["John Holland", "6-5", 27.0],
        ["R.J. Hunter", "6-5", 22.0],
        ["Jonas Jerebko", "6-10", 29.0],
        ["Amir Johnson", "6-9", 29.0],
        ["Jordan Mickey", "6-8", 21.0],
        ["Kelly Olynyk", "7-0", 25.0],
        ["Terry Rozier", "6-2", 22.0],
        ["Marcus Smart", "6-4", 22.0],
    ],
    columns=["Name", "Height", "Age"],
    pagination=True,
    search=True,
    sort=True,
)
```

```python
import pandas as pd

nba_data = pd.read_csv("data/nba.csv")
...
rx.data_table(
    data=nba_data[["Name", "Height", "Age"]],
    pagination=True,
    search=True,
    sort=True,
)
```

📊 **Dataset source:** [nba.csv](https://media.geeksforgeeks.org/wp-content/uploads/nba.csv)

The example below shows how to create a data table from from a list.

```python
class State(rx.State):
    data: List = [["Lionel", "Messi", "PSG"], ["Christiano", "Ronaldo", "Al-Nasir"]]
    columns: List[str] = ["First Name", "Last Name"]


def index():
    return rx.data_table(
        data=State.data,
        columns=State.columns,
    )
```

## Related

Explore the other ways to work with tabular data in Reflex, all in pure Python:

- [Table](/docs/library/tables-and-data-grids/table)
- [Data Editor](/docs/library/tables-and-data-grids/data-editor)
- [Tables and Data Grids](/docs/library/tables-and-data-grids/)
