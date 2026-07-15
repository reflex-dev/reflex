---
meta_description: "Display hierarchical data in AG Grid with Reflex. Build tree views like file explorers with expandable rows, group aggregation, and custom data paths in pure Python."
title: Tree Data
---

# Tree Data

Tree data displays hierarchical data — like a file system — with expandable and collapsible nodes. Each row provides a *path* (an array like `["Documents", "Projects", "file.txt"]`) that determines its position in the tree.

To enable it, set `tree_data=True` and tell the grid where to find the path with either `data_path_key` or `get_data_path` (specify exactly one, not both).

## Simple Case: `data_path_key`

When a field in the row data already contains the path array, pass its name as a string via `data_path_key`:

```python
import reflex as rx
import reflex_enterprise as rxe


class TreeDataState(rx.State):
    data: list[dict] = [
        {
            "path": ["Documents", "Projects", "file1.txt"],
            "size": 1024,
            "created": "2023-10-01",
        },
        {
            "path": ["Documents", "Projects", "subfolder", "file2.py"],
            "size": 2048,
            "created": "2023-10-02",
        },
        {
            "path": ["Downloads", "image.jpg"],
            "size": 512000,
            "created": "2023-10-03",
        },
    ]


def tree_grid_simple():
    return rxe.ag_grid(
        id="tree_grid_simple",
        row_data=TreeDataState.data,
        tree_data=True,
        data_path_key="path",
        auto_group_column_def={
            "headerName": "File Path",
            "minWidth": 280,
            "cellRendererParams": {"suppressCount": True},
        },
        column_defs=[
            {"field": "size", "aggFunc": "sum"},
            {"field": "created"},
        ],
        group_default_expanded=0,  # 0 = collapsed, -1 = all expanded
        width="100%",
        height="500px",
    )
```

Key configuration:

- `auto_group_column_def` configures the tree column (the one with the expand/collapse arrows).
- `group_default_expanded` controls the initial expansion: `0` for collapsed, `-1` for fully expanded, or a positive number for the depth to expand to.
- `aggFunc` on value columns aggregates values at the group level (e.g. total size of a folder).

## Custom Paths: `get_data_path`

For anything beyond reading a single field, pass a JavaScript function as `get_data_path`. It must be built with `rx.vars.function.ArgsFunctionOperation` and cast to `rx.vars.FunctionVar`:

```python
def tree_grid_custom():
    return rxe.ag_grid(
        id="tree_grid_custom",
        row_data=TreeDataState.data,
        tree_data=True,
        get_data_path=rx.vars.function.ArgsFunctionOperation.create(
            ["data"],
            rx.Var("data.path"),
        ).to(rx.vars.FunctionVar),
        auto_group_column_def={"headerName": "File Path", "minWidth": 280},
        column_defs=[
            {"field": "size", "aggFunc": "sum"},
            {"field": "created"},
        ],
        group_default_expanded=0,
        width="100%",
        height="500px",
    )
```

The function receives the row `data` and must return the array representing the row's position in the hierarchy. The JavaScript expression can build the array on the fly, e.g. `rx.Var("[data.host, ...data.path]")` to prefix each path with a host name.

```md alert warning
# Pass `get_data_path` directly as a grid prop — never define it as a state var or computed var.
Returning the function from an `@rx.var` (or storing it in state) raises `Invalid var passed for prop WrappedAgGrid.get_data_path`. Build the `ArgsFunctionOperation` inline in the `rxe.ag_grid(...)` call.
```

### Switching Paths Dynamically

`get_data_path` can be selected at render time with `rx.cond`. Give the grid a `key` derived from the condition so it re-initializes when the path logic changes:

```python
class TreeDisplayState(rx.State):
    combine_hosts: bool = True
    data: list[dict] = [
        {"host": "server1", "path": ["Documents", "file1.txt"], "size": 1024},
        {"host": "server2", "path": ["Downloads", "file2.pdf"], "size": 2048},
    ]


def tree_grid_conditional():
    return rxe.ag_grid(
        id="tree_grid_conditional",
        row_data=TreeDisplayState.data,
        tree_data=True,
        get_data_path=rx.cond(
            TreeDisplayState.combine_hosts,
            rx.vars.function.ArgsFunctionOperation.create(
                ["data"],
                rx.Var("data.path"),
            ),
            rx.vars.function.ArgsFunctionOperation.create(
                ["data"],
                rx.Var("[data.host, ...data.path]"),
            ),
        ).to(rx.vars.FunctionVar),
        key=f"grid_{TreeDisplayState.combine_hosts}",
        auto_group_column_def={"headerName": "File Explorer", "minWidth": 280},
        column_defs=[{"field": "size", "aggFunc": "sum"}],
        width="100%",
        height="500px",
    )
```

## Formatting Aggregated Values

Value formatters work on tree columns too. For example, human-readable file sizes:

```python
human_size = rx.vars.function.ArgsFunctionOperation.create(
    ["params"],
    rx.Var("""{
        const sizeInKb = params.value / 1024;
        if (sizeInKb > 1024) {
            return `${+(sizeInKb / 1024).toFixed(2)} MB`;
        } else {
            return `${+sizeInKb.toFixed(2)} KB`;
        }
    }"""),
)

column_defs = [
    {"field": "size", "aggFunc": "sum", "value_formatter": human_size},
]
```
