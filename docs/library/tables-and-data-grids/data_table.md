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

If you want to [add, edit or remove data](/docs/library/tables-and-data-grids/table/) in your app or deal with anything but static data then the [`rx.table`](/docs/library/tables-and-data-grids/table/) might be a better fit for your use case.

## Basic Example

The data_table component displays tabular data with optional search, sorting, and pagination features.

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

## Using pandas DataFrames

The data_table component works seamlessly with pandas DataFrames. Pass the DataFrame directly to the `data` prop and the column names are extracted automatically.

```python
import pandas as pd
import reflex as rx

nba_data = pd.read_csv("data/nba.csv")


def index():
    return rx.data_table(
        data=nba_data[["Name", "Height", "Age"]],
        pagination=True,
        search=True,
        sort=True,
    )
```

📊 **Dataset source:** [nba.csv](https://media.geeksforgeeks.org/wp-content/uploads/nba.csv)

## Sorting

Enable sorting by setting `sort=True`. Users can click column headers to sort ascending or descending.

```python
rx.data_table(
    data=nba_data[["Name", "Team", "Salary"]],
    sort=True,
)
```

You can also programmatically control the default sort order in your state:

```python
class TableState(rx.State):
    data: pd.DataFrame = pd.read_csv("data/nba.csv")

    @rx.var
    def sorted_data(self) -> pd.DataFrame:
        return self.data.sort_values("Name")


def index():
    return rx.data_table(
        data=TableState.sorted_data,
        sort=True,
    )
```

## Pagination

Enable pagination by setting `pagination=True`. This automatically splits large datasets into pages and adds navigation controls. By default, the table shows 10 rows per page.

```python
rx.data_table(
    data=nba_data,
    pagination=True,
)
```

## Search

Enable search by setting `search=True`. The search box filters rows across all columns in real time as the user types.

```python
rx.data_table(
    data=nba_data,
    search=True,
)
```

Search is case-insensitive and matches partial strings. When combined with pagination, search results are automatically paginated.

## Complete Example with State

The example below builds a data table from rows and columns stored in state. Any event handler that updates `TableState.data` re-renders the table.

```python
import reflex as rx


class TableState(rx.State):
    data: list[list[str]] = [
        ["Lionel", "Messi", "Argentina"],
        ["Cristiano", "Ronaldo", "Portugal"],
        ["Neymar", "Jr", "Brazil"],
        ["Kylian", "Mbappé", "France"],
    ]
    columns: list[str] = ["First Name", "Last Name", "Country"]


def index():
    return rx.data_table(
        data=TableState.data,
        columns=TableState.columns,
        pagination=True,
        search=True,
        sort=True,
    )
```

## Related

Explore the other ways to work with tabular data in Reflex, all in pure Python:

- [Table](/docs/library/tables-and-data-grids/table/) — Composable semantic table for custom layouts
- [Data Editor](/docs/library/tables-and-data-grids/data-editor/) — Spreadsheet-style editable data grid
- [Tables and Data Grids](/docs/library/tables-and-data-grids/) — Overview of all table components
- [AG Grid](/docs/enterprise/ag-grid/) — Enterprise data grid with advanced features
