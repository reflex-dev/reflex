---
title: Linked XY Charts and Cross-Filtering in Python with Reflex
meta_description: Link XY charts and a table in Reflex. Use chart selection events and shared Python state to cross-filter related views and reset selected records.
---

# Build linked XY charts with shared state

You can link XY charts in Reflex by storing a selection in application state and deriving the data displayed by other components from it. In this tutorial, selecting points in an XY scatter chart filters an XY bar chart and a table. Reset restores all records.

This is cross-filtering through Python state. XY also supports browser-side axis linking through `link_group` and `link_axes`; synchronized zoom is a different behavior from filtering records. The example below sends a completed selection to a Python handler rather than attaching Python work to every hover.

## Install and configure XY

Start with a blank project using the [installation guide](/docs/getting-started/installation/). This example uses Python 3.11 or newer and the XY 0.0.7 Reflex integration:

```bash
uv add "xy[reflex]==0.0.7"
```

Register the XY plugin in `rxconfig.py`. Keep your app's existing name and other plugins:

```python
import reflex as rx
import reflex_xy as rxy

config = rx.Config(
    app_name="linked_dashboard",
    plugins=[rxy.XYPlugin()],
)
```

The plugin connects XY's data channel to your Reflex app. Use state-backed chart data for event handlers: a static chart does not provide the same backend event connection. See the [XY Reflex integration](https://reflex.dev/docs/xy/integrations/reflex/) for the supported chart tiers.

## Run the example

Copy the following code into your app module. The four-record dataset is fixed, so selections can be mapped to stable application IDs without a database or credentials.

```python demo exec defer id=linked_charts_demo
from typing import TypedDict

import reflex as rx
import reflex_xy as rxy
import xy


RECORDS = [
    {"id": "order-a", "hours": 2, "revenue": 120},
    {"id": "order-b", "hours": 4, "revenue": 180},
    {"id": "order-c", "hours": 6, "revenue": 90},
    {"id": "order-d", "hours": 8, "revenue": 240},
]


class OrderColumns(TypedDict):
    hours: list[int]
    revenue: list[int]


class RevenueColumns(TypedDict):
    order: list[str]
    revenue: list[int]


class LinkedChartsState(rx.State):
    # None means no filter; an empty list means a selection with no matches.
    selected_ids: list[str] | None = None
    chart_revision: int = 0
    selection_error: str = ""

    @rxy.data(cache=False)
    def source_data(self) -> OrderColumns:
        """Provide the fixed source trace through XY's live data channel."""
        return {
            "hours": [row["hours"] for row in RECORDS],
            "revenue": [row["revenue"] for row in RECORDS],
        }

    @rx.event
    def select_points(self, event: rxy.SelectEndEvent):
        """Map canonical source rows to stable application record IDs."""
        selection = event["selection"]
        self.selection_error = ""
        if selection["cleared"]:
            self.selected_ids = None
            return
        rows = selection["rows"]
        if selection["truncated"]:
            resolved = rxy.resolve_selection(event)
            if resolved is None:
                self.selection_error = "Selection unavailable. Please select again."
                return
            rows = resolved.rows()
        self.selected_ids = list(
            dict.fromkeys(
                RECORDS[row["index"]]["id"]
                for row in rows
                if row.get("trace") == 0
                and type(row.get("index")) is int
                and 0 <= row["index"] < len(RECORDS)
            )
        )

    @rx.event
    def clear_selection(self):
        """Restore all records and remount the source chart to clear highlights."""
        self.selected_ids = None
        self.selection_error = ""
        self.chart_revision += 1

    @rx.var
    def visible_rows(self) -> list[dict]:
        """Return all records or the currently selected subset."""
        if self.selected_ids is None:
            return RECORDS
        selected = set(self.selected_ids)
        return [row for row in RECORDS if row["id"] in selected]

    @rxy.data(cache=False)
    def revenue_data(self) -> RevenueColumns:
        """Supply the linked chart from the same rows as the table."""
        return {
            "order": [row["id"] for row in self.visible_rows],
            "revenue": [row["revenue"] for row in self.visible_rows],
        }


def linked_charts():
    """Render an XY source chart, linked bar chart, and selected records."""
    return rx.vstack(
        rx.text("Drag a box around points to filter the chart and table."),
        rxy.scatter_chart(
            data=LinkedChartsState.source_data,
            x="hours",
            y="revenue",
            size=10,
            color="#6e56cf",
            select=True,
            default_drag_action="select",
            on_select_end=LinkedChartsState.select_points,
            x_axis=xy.x_axis(label="Hours"),
            y_axis=xy.y_axis(label="Revenue"),
            key=LinkedChartsState.chart_revision.to(str),
            width="100%",
            height="280px",
        ),
        rx.button("Reset selection", on_click=LinkedChartsState.clear_selection),
        rx.text("Visible records: ", LinkedChartsState.visible_rows.length()),
        rx.text(LinkedChartsState.selection_error, role="alert", color="red"),
        rxy.bar_chart(
            data=LinkedChartsState.revenue_data,
            x="order",
            y="revenue",
            color="#6e56cf",
            x_axis=xy.x_axis(label="Order"),
            y_axis=xy.y_axis(label="Revenue"),
            width="100%",
            height="280px",
        ),
        rx.cond(
            LinkedChartsState.visible_rows.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Order"),
                        rx.table.column_header_cell("Hours"),
                        rx.table.column_header_cell("Revenue"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        LinkedChartsState.visible_rows,
                        lambda row: rx.table.row(
                            rx.table.cell(row["id"]),
                            rx.table.cell(row["hours"]),
                            rx.table.cell(row["revenue"]),
                        ),
                    )
                ),
                width="100%",
            ),
            rx.text("No records match this selection. Reset to see all orders."),
        ),
        width="100%",
        spacing="4",
    )
```

Add these lines at the end of the module, then run `uv run reflex run`:

```python
app = rx.App()
app.add_page(linked_charts)
```

## How the views stay linked

1. `source_data` supplies the full, fixed trace through `@rxy.data`.
2. XY's `on_select_end` event supplies a selection envelope with canonical row information, a count, and clear/truncation flags.
3. The handler maps selected source row indexes to application IDs and stores them in `selected_ids`.
4. The table reads `visible_rows`; `revenue_data` supplies those same rows to the XY bar chart.
5. Reset clears the filter and changes the source chart's key so its selection highlight clears too. Remounting also resets that chart's zoom.

The demo uses `cache=False` for these tiny datasets so an empty pre-session data handle is recomputed after hydration. For expensive queries, cache the query results separately rather than rerunning them for every event.

XY's numeric chart columns travel through its data channel. The table's four displayed records remain ordinary Reflex state. Choosing XY for the chart does not remove the need to paginate a large table.

## Empty selections and bounded events

A cleared selection means “remove the filter,” so `selected_ids` becomes `None`. A completed box containing no points means an empty result, so it becomes `[]`. These states must not be conflated.

Selection event rows are bounded. The handler uses `resolve_selection` when `truncated` is true rather than silently filtering to only the rows included in the event. This tiny example does not reach that limit, but the branch matters when adapting it to larger data. If the chart registry can no longer resolve the selection, the example retains the previous filter and asks the user to select again.

The Reflex adapter event is distinct from a notebook's `xy.Selection` callback. See [XY interactions and selections](https://reflex.dev/docs/xy/core-concepts/interactions/) for both contracts.

## Preserve record identity

XY returns canonical source row positions, including when a rendering representation differs from the original rows. Those positions are still not database primary keys. This example maps trace zero's `index` through the fixed `RECORDS` sequence to obtain an application ID.

If you reorder or replace the source data, maintain the exact row-ID mapping for that displayed generation. Account for selection events that arrive during a refresh, and reject stale generations rather than mapping an old index against new records. For multiple traces, keep the mapping for each trace. The linked chart can change independently here because the source trace remains fixed.

## Link axes without cross-filtering

For charts with compatible axes, give them the same `link_group` and select `link_axes`, such as `("x",)`, to synchronize their view in the browser. Use that for a shared time window. Use the state/event pattern above when a selection must change records in another chart or table.

The source chart here uses hours, while the bar chart uses order IDs. Their x axes are not compatible, so they deliberately do not share an axis-link group.

## Check the behavior

Select the first two points: the table should show `order-a` and `order-b`, and the bar chart should show revenues 120 and 180. Select a different region and verify the old rows disappear. Select an empty region and verify the empty-result message. Reset and verify that all four rows return and the highlight clears. Open a separate browser session and check that one session's selection does not change the other.

## Larger datasets

Keep the original row-ID mapping on the backend, authorize data access there, and query or aggregate only what the views need. Do not serialize a huge resolved selection into frontend state merely because the chart can render a large dataset. Choose a query or selection representation appropriate to the data source and paginate the table.

Continue with [dashboards and internal tools](/docs/guides/dashboards-and-internal-tools/) and [performance and execution](/docs/advanced-onboarding/performance-and-execution/).
