---
title: "Cell Selection"
order: 8
---

```python exec
from pcweb.pages.docs import enterprise
```

# Cell Selection

AG Grid provides powerful cell selection capabilities that allow users to select individual cells or ranges of cells. This feature is essential for data manipulation, copying, and advanced interactions like fill handle operations.

## Range Selection

To enable cell selection in your AG Grid, set the `cell_selection` prop to `True`. This automatically enables both single cell selection and range selection capabilities.

### Basic Selection Example

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import pandas as pd

class CellSelectionState(rx.State):
    data: list[dict] = []

    @rx.event
    def load_data(self):
        df = pd.read_json("https://www.ag-grid.com/example-assets/olympic-winners.json")
        self.data = df.head(10).to_dict("records")

    @rx.event
    def echo_selection(self, ranges: list[dict], started: bool, finished: bool):
        if finished:
            yield rx.toast(f"Selected ranges: {ranges}")

column_defs = [
    {"field": "athlete", "width": 150},
    {"field": "age", "width": 90},
    {"field": "country", "width": 120},
    {"field": "year", "width": 90},
    {"field": "sport", "width": 120},
    {"field": "gold", "width": 100},
    {"field": "silver", "width": 100},
    {"field": "bronze", "width": 100},
]

def basic_cell_selection():
    return rx.vstack(
        rx.text("Click and drag to select cells. Selection info will appear in a toast.", size="2"),
        rxe.ag_grid(
            id="basic_cell_selection_grid",
            column_defs=column_defs,
            row_data=CellSelectionState.data,
            cell_selection=True,
            on_cell_selection_changed=CellSelectionState.echo_selection,
            width="100%",
            height="400px",
        ),
        on_mount=CellSelectionState.load_data,
        width="100%",
    )
```

### Advanced Selection Event Handling

For more sophisticated selection handling, you can process the selection ranges to calculate detailed information:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import pandas as pd

class AdvancedSelectionState(rx.State):
    data: list[dict] = []

    @rx.event
    def load_data(self):
        df = pd.DataFrame({
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "score": [85, 92, 78, 96, 88],
            "grade": ["B", "A", "C", "A", "B"],
            "attempts": [3, 2, 4, 1, 3]
        })
        self.data = df.to_dict("records")

    @rx.event
    def handle_selection(self, ranges: list[dict], started: bool, finished: bool):
        if finished and ranges:
            total_cells = sum(
                (r.get("endRow", 0) - r.get("startRow", 0) + 1) * 
                len(r.get("columns", []))
                for r in ranges
            )
            yield rx.toast(f"Selected {total_cells} cells across {len(ranges)} ranges")

editable_column_defs = [
    {"field": "name", "width": 120},
    {"field": "score", "width": 100, "editable": True},
    {"field": "grade", "width": 100, "editable": True},
    {"field": "attempts", "width": 120, "editable": True},
]

def advanced_selection_example():
    return rx.vstack(
        rx.text("Select ranges of cells. Try selecting multiple ranges by holding Ctrl/Cmd.", size="2"),
        rxe.ag_grid(
            id="advanced_selection_grid",
            column_defs=editable_column_defs,
            row_data=AdvancedSelectionState.data,
            cell_selection=True,
            on_cell_selection_changed=AdvancedSelectionState.handle_selection,
            width="100%",
            height="300px",
        ),
        on_mount=AdvancedSelectionState.load_data,
        width="100%",
    )
```

## Fill Handle

The fill handle is a powerful feature that allows users to quickly fill cells by dragging from a selected cell or range. When enabled, a small square appears at the bottom-right corner of the selection that users can drag to fill adjacent cells.

### Enabling Fill Handle

To enable the fill handle, configure the `cell_selection` prop with a dictionary containing the handle configuration:

```python
cell_selection={
    "handle": {
        "mode": "fill",  # Enable fill handle
    }
}
```

### Fill Handle Events

When using the fill handle, it will trigger `on_cell_value_changed` for each cell receiving a fill value. This allows your backend to handle the data changes appropriately.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import pandas as pd

class FillHandleState(rx.State):
    data: list[dict] = []
    change_log: list[str] = []

    @rx.event
    def load_data(self):
        df = pd.DataFrame({
            "item": ["Apple", "Banana", "Cherry", "Date", "Elderberry"],
            "quantity": [10, 15, 8, 12, 20],
            "price": [1.50, 0.75, 2.00, 3.00, 4.50],
            "total": [15.00, 11.25, 16.00, 36.00, 90.00]
        })
        self.data = df.to_dict("records")

    @rx.event
    def handle_cell_change(self, data: dict):
        row_index = data.get("rowIndex", 0)
        field = data.get("colId", "")
        new_value = data.get("newValue", "")
        old_value = data.get("oldValue", "")
        
        change_msg = f"Row {row_index + 1}, {field}: '{old_value}' → '{new_value}'"
        self.change_log = [change_msg] + self.change_log[:9]  # Keep last 10 changes
        
        # Update the data
        if 0 <= row_index < len(self.data):
            self.data[row_index][field] = new_value

fill_column_defs = [
    {"field": "item", "width": 120},
    {"field": "quantity", "width": 100, "editable": True, "type": "numericColumn"},
    {"field": "price", "width": 100, "editable": True, "type": "numericColumn"},
    {"field": "total", "width": 100, "editable": True, "type": "numericColumn"},
]

def fill_handle_example():
    return rx.vstack(
        rx.text("Select a cell and drag the fill handle (small square at bottom-right) to fill adjacent cells.", size="2"),
        rxe.ag_grid(
            id="fill_handle_grid",
            column_defs=fill_column_defs,
            row_data=FillHandleState.data,
            cell_selection={
                "handle": {
                    "mode": "fill",  # Enable fill handle
                }
            },
            on_cell_value_changed=FillHandleState.handle_cell_change,
            width="100%",
            height="300px",
        ),
        rx.divider(),
        rx.text("Recent Changes:", weight="bold", size="3"),
        rx.cond(
            FillHandleState.change_log,
            rx.vstack(
                rx.foreach(
                    FillHandleState.change_log,
                    lambda change: rx.text(change, size="1", color="gray")
                ),
                spacing="1",
            ),
            rx.text("No changes yet", size="2", color="gray")
        ),
        on_mount=FillHandleState.load_data,
        width="100%",
        spacing="4",
    )
```

## Advanced Configuration Options

You can further customize cell selection behavior using additional configuration options:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import pandas as pd

class ConfigurationState(rx.State):
    data: list[dict] = []

    @rx.event
    def load_data(self):
        df = pd.DataFrame({
            "id": range(1, 8),
            "name": ["Product A", "Product B", "Product C", "Product D", "Product E", "Product F", "Product G"],
            "category": ["Electronics", "Clothing", "Electronics", "Books", "Clothing", "Electronics", "Books"],
            "price": [299.99, 49.99, 199.99, 24.99, 79.99, 399.99, 19.99],
            "stock": [15, 32, 8, 45, 23, 12, 67]
        })
        self.data = df.to_dict("records")

configuration_column_defs = [
    {"field": "id", "width": 80},
    {"field": "name", "width": 150, "editable": True},
    {"field": "category", "width": 120},
    {"field": "price", "width": 100, "editable": True, "type": "numericColumn"},
    {"field": "stock", "width": 100, "editable": True, "type": "numericColumn"},
]

def configuration_example():
    return rx.vstack(
        rx.text("Cell selection with additional configuration options", size="2"),
        rxe.ag_grid(
            id="configuration_grid",
            column_defs=configuration_column_defs,
            row_data=ConfigurationState.data,
            cell_selection={
                "handle": {
                    "mode": "fill",
                }
            },
            enable_cell_text_selection=True,  # Allow text selection within cells
            suppress_cell_focus=False,  # Allow cell focus
            width="100%",
            height="350px",
        ),
        on_mount=ConfigurationState.load_data,
        width="100%",
    )
```

## Key Features

- **Cell Selection**: Enable with `cell_selection=True` for both single cell and range selection capabilities
- **Fill Handle**: Configure with `cell_selection={"handle": {"mode": "fill"}}` for drag-to-fill functionality
- **Event Handling**: Use `on_cell_selection_changed` to respond to selection changes
- **Value Changes**: Use `on_cell_value_changed` to handle individual cell edits and fill operations
- **Text Selection**: Enable `enable_cell_text_selection=True` to allow text selection within cells

## Best Practices

1. **Use cell_selection configuration**: Both single cell and range selection are automatically enabled with `cell_selection=True`, providing all necessary selection capabilities for fill operations.

2. **Handle cell value changes**: When using fill handle, implement `on_cell_value_changed` to process the data updates in your backend.

3. **Provide user feedback**: Use toasts or other UI elements to confirm selection actions and data changes.

4. **Consider performance**: For large datasets, be mindful of the performance impact of frequent cell value change events.

5. **Validate fill operations**: Implement validation logic in your `on_cell_value_changed` handler to ensure data integrity.
