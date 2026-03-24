---
order: 1
---

```python exec
from pcweb.pages.docs import enterprise
```

# Column Definitions

## Basic Columns

AgGrid allows you to define the columns of your grid, passed to the prop `column_defs`. Each dictionary represents a column.

```md alert warning
# If you are converting from other AG Grid implementation, we also support camelCase for the name of the properties.
```

Here we define a grid with 3 columns:
```python
column_defs = [
    {"field": "direction"},
    {"field": "strength"},
    {"field": "frequency"},
]
```

To set default properties for all your columns, you can define `default_col_def` in your grid:
```python
default_col_def = {
    "sortable": True,
    "filter": True,
    "resizable": True,
}
```