```python exec
import reflex as rx
```

# Filtered Table

## Recipe

```python eval
rx.center(rx.image(src="/gallery/filtered_table.gif"))
```

This recipe uses an `rx.foreach` for the row generation with a computed var filtering the data for rows, using an input value for filter value.

Additionally, the filter input uses a debounce that limits the update, which prevents filtered data to be calculated on every keypress.

```python
import reflex as rx
from typing import List, Dict

RAW_DATA = [
    \{"name": "Alice", "tags": "tag1"},
    \{"name": "Bob", "tags": "tag2"},
    \{"name": "Charlie", "tags": "tag1"},
]
RAW_DATA_COLUMNS = ["Name", "tags"]


class FilteredTableState(rx.State):
    filter_expr: str = ""
    data: Dict[str, Dict[str, str]] = RAW_DATA

    @rx.cached_var
    def filtered_data(self) -> List[Dict[str, str]]:
        # Use this generated filtered data view in the `rx.foreach` of
        #  the table renderer of rows
        # It is dependent on `filter_expr`
        # This `filter_expr` is set by an rx.chakra.input
        return [
            row
            for row in self.data
            if self.filter_expr == ""
            or self.filter_expr != ""
            and self.filter_expr == row["tags"]
        ]

    def input_filter_on_change(self, value):
        self.filter_expr = value
        # for DEBUGGING
        yield rx.console_log(f"Filter set to: \{self.filter_expr}")


def render_row(row):
    return rx.chakra.tr(rx.chakra.td(row["name"]), rx.chakra.td(row["tags"]))


def render_rows():
    return [
        rx.foreach(
            # use data filtered by `filter_expr` as update by rx.chakra.input
            FilteredTableState.filtered_data,
            render_row,
        )
    ]


def render_table():
    return rx.chakra.table_container(
        rx.chakra.table(
            rx.chakra.thead(rx.chakra.tr(*[rx.chakra.th(column) for column in RAW_DATA_COLUMNS])),
            rx.chakra.tbody(*render_rows()),
        )
    )


def index() -> rx.Component:
    return rx.box(
        rx.box(
            rx.heading(
                "Filter by tags:",
                size="sm",
            ),
            rx.chakra.input(
                on_change=FilteredTableState.input_filter_on_change,
                value=FilteredTableState.filter_expr,
                debounce_timeout=1000,
            ),
        ),
        rx.box(
            render_table(),
        ),
    )


app = rx.App()
app.add_page(index, route="/")

```
