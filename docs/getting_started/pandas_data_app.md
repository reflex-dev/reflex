---
title: Build a Pandas Data App with Reflex
meta_description: Turn pandas analysis into a Python web app. Upload a CSV, filter records, aggregate by region, preview rows, and download the filtered summary with Reflex.
---

# Build a pandas data app

Use Reflex to turn pandas analysis into a shareable Python web app with a custom interface. This example uploads a CSV, filters its records, groups units by region, and downloads the filtered summary. Summary cards, an XY bar chart, and a table update together from the filtered data. The parsing and analysis functions remain ordinary Python functions.

Try the live sample below: select a region or search for a product, then apply the filters to update the cards, chart, and table. The complete app runs locally without a database or API key. CSV uploads run in your own app; the embedded preview uses sample data.

## Set up the app

Create a blank app using the [installation guide](/docs/getting-started/installation/), then install pandas and XY with Python 3.11 or newer:

```bash
uv add pandas "xy[reflex]==0.0.7"
```

Register the XY plugin in `rxconfig.py`, keeping your app's existing name and other plugins:

```python
import reflex as rx
import reflex_xy as rxy

config = rx.Config(
    app_name="pandas_data",
    plugins=[rxy.XYPlugin()],
)
```

The CSV must contain exactly `region,product,units` in that order. Regions are North, South, East, or West. Products are nonempty text up to 80 characters, and units are whole numbers from 0 to 1,000,000. Files must be UTF-8, at most 2 MiB, and contain 1–10,000 records.

Save this as `orders.csv` to try uploading:

```csv
region,product,units
North,Tea,12
South,Coffee,7
North,Coffee,5
West,Tea,9
```

## Copy the complete example

Paste this code into your app module. It shows at most 50 matching records in the browser; the summary and download include all matching records within the upload limit.

```python demo exec defer id=pandas_data_app
import asyncio
import csv
from io import StringIO
from itertools import islice
from typing import Any, TypedDict

import pandas as pd
import reflex as rx
import reflex_xy as rxy
import xy


REGIONS = ["North", "South", "East", "West"]
MAX_CSV_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10_000
UPLOAD_ID = "orders-csv"
SAMPLE_CSV = (
    b"region,product,units\nNorth,Tea,12\nSouth,Coffee,7\nNorth,Coffee,5\nWest,Tea,9\n"
)


class OrderRow(TypedDict):
    region: str
    product: str
    units: int


class RegionTotal(TypedDict):
    region: str
    units: int


class RegionColumns(TypedDict):
    region: list[str]
    units: list[int]


def read_orders(data: bytes) -> list[OrderRow]:
    """Parse a bounded CSV and validate its columns and record values."""
    if len(data) > MAX_CSV_BYTES:
        raise ValueError("Choose a CSV of at most 2 MiB.")
    try:
        reader = csv.reader(StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        nonempty_rows = (row for row in reader if row)
        columns = next(nonempty_rows, [])
        rows = list(islice(nonempty_rows, MAX_ROWS + 1))
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValueError(
            "Choose a valid UTF-8 CSV with three columns per row."
        ) from error
    if not columns or not rows:
        raise ValueError("The CSV needs a header and at least one record.")
    if columns != ["region", "product", "units"]:
        raise ValueError("Use exactly these columns: region,product,units.")
    if len(rows) > MAX_ROWS:
        raise ValueError("Include between 1 and 10,000 records.")
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("Use exactly three columns per row.")
    frame = pd.DataFrame(rows, columns=columns)
    frame["region"] = frame["region"].str.strip()
    frame["product"] = frame["product"].str.strip()
    frame["units"] = frame["units"].str.strip()
    if not frame["region"].isin(REGIONS).all():
        raise ValueError("Regions must be North, South, East, or West.")
    if not frame["product"].str.len().between(1, 80).all():
        raise ValueError("Each product must contain 1–80 characters.")
    if not frame["units"].str.fullmatch(r"[0-9]{1,7}").all():
        raise ValueError("Units must be whole numbers from 0 to 1,000,000.")
    frame["units"] = pd.to_numeric(frame["units"])
    if not frame["units"].between(0, 1_000_000).all():
        raise ValueError("Units must be whole numbers from 0 to 1,000,000.")
    return frame.to_dict(orient="records")


def analyze_orders(
    records: list[OrderRow], region: str, product: str
) -> tuple[list[OrderRow], list[RegionTotal], int, int]:
    """Filter records and return a bounded preview plus complete aggregates."""
    frame = pd.DataFrame(records, columns=["region", "product", "units"])
    if frame.empty:
        return [], [], 0, 0
    if region != "All":
        frame = frame.loc[frame["region"] == region]
    matches = frame.loc[
        frame["product"].str.contains(product.strip(), case=False, regex=False)
    ]
    summary = matches.groupby("region", as_index=False, sort=True)["units"].sum()
    return (
        matches.head(50).to_dict(orient="records"),
        summary.to_dict(orient="records"),
        len(matches),
        int(matches["units"].sum()),
    )


class PandasAppState(rx.State):
    _orders: list[OrderRow] = []
    rows: list[OrderRow] = []
    summary: list[RegionTotal] = []
    region: str = "All"
    product: str = ""
    matching_count: int = 0
    total_units: int = 0
    loaded_count: int = 0
    processing: bool = False
    error: str = ""

    def _refresh(self):
        """Apply the current filter to the session's backend-only records."""
        self.rows, self.summary, self.matching_count, self.total_units = analyze_orders(
            self._orders, self.region, self.product
        )
        self.loaded_count = len(self._orders)

    @rx.event
    def load_sample(self, clear_upload: bool = True):
        """Replace the dataset while retaining the applied filter."""
        if self.processing:
            return
        self._orders = read_orders(SAMPLE_CSV)
        self.error = ""
        self._refresh()
        if clear_upload:
            return rx.clear_selected_files(UPLOAD_ID)

    @rx.event
    async def upload_csv(self, files: list[rx.UploadFile]):
        """Read and parse one bounded upload, clearing stale data on failure."""
        if self.processing:
            return
        self._orders = []
        self._refresh()
        self.error = ""
        if len(files) != 1:
            self.error = "Choose one CSV file."
            return
        self.processing = True
        yield
        try:
            data = await files[0].read(MAX_CSV_BYTES + 1)
            self._orders = await asyncio.to_thread(read_orders, data)
        except ValueError as error:
            self.error = str(error)
        except OSError:
            self.error = "The file could not be read. Please try again."
        finally:
            self.processing = False
            self._refresh()

    @rx.event
    def apply_filters(self, form_data: dict[str, Any]):
        """Apply a region and literal, case-insensitive product search."""
        if self.processing:
            return
        region = str(form_data.get("region", "All"))
        product = str(form_data.get("product", "")).strip()
        if region not in ["All", *REGIONS] or len(product) > 80:
            self.error = "Choose a listed region and search with at most 80 characters."
            return
        self.region = region
        self.product = product
        self.error = ""
        self._refresh()

    @rxy.data(cache=False)
    def region_data(self) -> RegionColumns:
        """Publish the complete filtered regional totals to the XY chart."""
        return {
            "region": [row["region"] for row in self.summary],
            "units": [row["units"] for row in self.summary],
        }

    @rx.event
    def download_summary(self):
        """Download the complete regional aggregate for the applied filter."""
        if self.processing or not self.summary:
            return
        csv = pd.DataFrame(self.summary, columns=["region", "units"]).to_csv(
            index=False
        )
        return rx.download(
            data=csv, filename="region-summary.csv", mime_type="text/csv"
        )


def metric_card(label: str, value: rx.Var[int], icon: str):
    """Render one labelled aggregate alongside a decorative icon.

    Args:
        label: The metric's visible name.
        value: Its current state value.
        icon: The icon name.

    Returns:
        A card with a large numeric value.
    """
    return rx.box(
        rx.hstack(
            rx.text(label, size="2", color=rx.color("gray", 11)),
            rx.center(
                rx.icon(icon, size=17, aria_hidden=True),
                width="2rem",
                height="2rem",
                border_radius="10px",
                color=rx.color("violet", 11),
                background=rx.color("violet", 3),
            ),
            justify="between",
            width="100%",
        ),
        rx.text(value, size="8", weight="bold", letter_spacing="-0.04em"),
        width="100%",
        padding="1rem 1.25rem",
        background=rx.color("gray", 1),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="14px",
        box_shadow="0 2px 6px rgba(0, 0, 0, 0.025)",
    )


def pandas_data_app(show_upload: bool = True):
    """Render the order dashboard with optional local CSV upload controls.

    Args:
        show_upload: Include upload controls in the standalone app.

    Returns:
        Filters, metric cards, a chart, and matching records.
    """
    return rx.vstack(
        rx.flex(
            rx.vstack(
                rx.hstack(
                    rx.icon("chart-no-axes-combined", size=14, aria_hidden=True),
                    rx.text(
                        "SALES ANALYTICS",
                        size="1",
                        weight="bold",
                        letter_spacing="0.12em",
                    ),
                    color=rx.color("violet", 11),
                    spacing="2",
                    align="center",
                ),
                rx.heading(
                    "Order explorer", size="7", as_="h2", letter_spacing="-0.04em"
                ),
                rx.text(
                    "A closer look at your products and regions.",
                    size="2",
                    color=rx.color("gray", 11),
                ),
                spacing="2",
                align_items="start",
            ),
            rx.button(
                rx.icon("rotate-ccw", size=14, aria_hidden=True),
                "Use sample data",
                on_click=PandasAppState.load_sample(show_upload),
                disabled=PandasAppState.processing,
                variant="outline",
                color_scheme="gray",
                size="2",
                cursor="pointer",
            ),
            justify="between",
            align="start",
            gap="1rem",
            flex_wrap="wrap",
            width="100%",
        ),
        *(
            [
                rx.upload(
                    rx.vstack(
                        rx.text("Drop a CSV here or choose a file", weight="medium"),
                        rx.text("UTF-8 · up to 2 MiB · 10,000 rows", size="2"),
                        rx.foreach(
                            rx.selected_files(UPLOAD_ID), lambda name: rx.text(name)
                        ),
                        spacing="2",
                    ),
                    id=UPLOAD_ID,
                    accept={"text/csv": [".csv"]},
                    multiple=False,
                    disabled=PandasAppState.processing,
                    width="100%",
                    padding="1.5rem",
                    border=f"1px dashed {rx.color('gray', 7)}",
                    border_radius="8px",
                    overflow_wrap="anywhere",
                ),
                rx.button(
                    "Load CSV",
                    on_click=PandasAppState.upload_csv(
                        rx.upload_files(upload_id=UPLOAD_ID)
                    ),
                    loading=PandasAppState.processing,
                    disabled=rx.selected_files(UPLOAD_ID).length() == 0,
                ),
            ]
            if show_upload
            else []
        ),
        rx.cond(
            PandasAppState.error != "",
            rx.text(PandasAppState.error, role="alert", color=rx.color("red", 11)),
        ),
        rx.form(
            rx.grid(
                rx.vstack(
                    rx.el.label(
                        "Region",
                        html_for="order-region",
                        font_size="0.75rem",
                        font_weight="500",
                    ),
                    rx.el.select(
                        *[
                            rx.el.option(value, value=value)
                            for value in ["All", *REGIONS]
                        ],
                        id="order-region",
                        name="region",
                        default_value="All",
                        disabled=PandasAppState.processing,
                        padding="0.6rem 0.75rem",
                        height="40px",
                        width="100%",
                        min_width="0",
                        font_size="0.875rem",
                        border=f"1px solid {rx.color('gray', 7)}",
                        border_radius="8px",
                        background=rx.color("gray", 1),
                    ),
                    align_items="stretch",
                    min_width="0",
                    spacing="2",
                ),
                rx.vstack(
                    rx.el.label(
                        "Product contains",
                        html_for="order-product",
                        font_size="0.75rem",
                        font_weight="500",
                    ),
                    rx.input(
                        id="order-product",
                        name="product",
                        placeholder="Search products…",
                        width="100%",
                        min_width="0",
                        size="3",
                        max_length=80,
                        disabled=PandasAppState.processing,
                    ),
                    align_items="stretch",
                    min_width="0",
                    spacing="2",
                ),
                rx.button(
                    rx.icon("list-filter", size=16, aria_hidden=True),
                    "Apply filters",
                    type="submit",
                    color_scheme="violet",
                    cursor="pointer",
                    size="3",
                    align_self="end",
                    width="100%",
                    white_space="nowrap",
                    disabled=PandasAppState.processing,
                ),
                grid_template_columns="repeat(auto-fit, minmax(min(100%, 12rem), 1fr))",
                spacing="3",
                width="100%",
            ),
            on_submit=PandasAppState.apply_filters,
            width="100%",
            padding="1rem",
            background=rx.color("gray", 3),
            border_radius="12px",
        ),
        rx.grid(
            metric_card("Matching orders", PandasAppState.matching_count, "rows-3"),
            metric_card("Total units", PandasAppState.total_units, "package"),
            metric_card("Records loaded", PandasAppState.loaded_count, "database"),
            grid_template_columns="repeat(auto-fit, minmax(min(100%, 10rem), 1fr))",
            spacing="3",
            width="100%",
            role="status",
            aria_live="polite",
        ),
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.heading("Units by region", size="4", as_="h3"),
                    rx.text(
                        "Unit totals across all matching orders.",
                        size="2",
                        color=rx.color("gray", 11),
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.button(
                    rx.icon("download", size=14, aria_hidden=True),
                    "Download summary",
                    on_click=PandasAppState.download_summary,
                    disabled=PandasAppState.processing
                    | (PandasAppState.matching_count == 0),
                    variant="soft",
                    color_scheme="violet",
                    size="2",
                    cursor="pointer",
                ),
                justify="between",
                align="start",
                flex_wrap="wrap",
                gap="0.75rem",
                width="100%",
            ),
            rx.cond(
                PandasAppState.matching_count > 0,
                rxy.bar_chart(
                    data=PandasAppState.region_data,
                    x="region",
                    y="units",
                    color="#6e56cf",
                    x_axis=xy.x_axis(label="Region"),
                    y_axis=xy.y_axis(label="Units"),
                    width="100%",
                    height="280px",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("search", size=24, color=rx.color("gray", 9)),
                        rx.text("No matching orders", weight="medium"),
                        rx.text(
                            "Load data or try a different region or product.", size="2"
                        ),
                        align="center",
                    ),
                    min_height="200px",
                    background=rx.color("gray", 2),
                    border_radius="8px",
                ),
            ),
            rx.hstack(
                rx.foreach(
                    PandasAppState.summary,
                    lambda row: rx.badge(
                        row["region"],
                        ": ",
                        row["units"],
                        " units",
                        variant="soft",
                        size="2",
                    ),
                ),
                flex_wrap="wrap",
                gap="0.5rem",
                aria_label="Regional totals",
            ),
            spacing="4",
            align_items="stretch",
            padding=["1rem", "1.25rem"],
            background=rx.color("gray", 1),
            border=f"1px solid {rx.color('gray', 4)}",
            border_radius="14px",
            width="100%",
        ),
        rx.vstack(
            rx.heading("Matching orders", size="4", as_="h3"),
            rx.text(
                "Up to 50 matching rows · totals include every match",
                size="2",
                color=rx.color("gray", 11),
            ),
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(*[
                            rx.table.column_header_cell(
                                label, justify="end" if label == "Units" else "start"
                            )
                            for label in ["Region", "Product", "Units"]
                        ])
                    ),
                    rx.table.body(
                        rx.foreach(
                            PandasAppState.rows,
                            lambda row: rx.table.row(
                                rx.table.cell(
                                    rx.badge(
                                        row["region"],
                                        variant="soft",
                                        color_scheme="gray",
                                    )
                                ),
                                rx.table.cell(row["product"]),
                                rx.table.cell(
                                    row["units"],
                                    justify="end",
                                    font_variant_numeric="tabular-nums",
                                    font_weight="500",
                                ),
                            ),
                        )
                    ),
                    width="100%",
                ),
                width="100%",
                overflow_x="auto",
            ),
            rx.cond(
                PandasAppState.matching_count == 0,
                rx.text(
                    "No matching records. Load data or change the filters.", size="2"
                ),
            ),
            spacing="4",
            align_items="stretch",
            padding=["1rem", "1.25rem"],
            background=rx.color("gray", 1),
            border=f"1px solid {rx.color('gray', 4)}",
            border_radius="14px",
            width="100%",
        ),
        spacing="5",
        align_items="stretch",
        width="100%",
        min_width="0",
        max_width="54rem",
        margin="0 auto",
        padding=["1rem", "1.5rem"],
        background=rx.color("gray", 2),
        border=f"1px solid {rx.color('gray', 4)}",
        border_radius="18px",
    )


def pandas_preview():
    """Show the same dashboard with sample data and no upload controls."""
    return rx.box(
        pandas_data_app(show_upload=False),
        on_mount=PandasAppState.load_sample(False),
        width="100%",
    )
```

Register the page at the app root:

```python
app = rx.App()
app.add_page(pandas_data_app, route="/")
```

Run `uv run reflex run`. Select **Use sample data**: the cards show four matching records and 33 units; the chart shows North 17, South 7, and West 9. Filter for North and Tea: one record totals 12 units. Download the summary to get `North,12`. A search with no matches shows the chart's empty state, clears the table, and disables download. Uploading an invalid CSV clears the previous dataset and shows an error; a valid upload or the sample button lets you recover.

## Where pandas runs

`read_orders` parses and validates the upload on the backend. Parsing runs in a worker thread; the upload handler shows progress before awaiting it. `analyze_orders` uses a pandas DataFrame for literal text filtering and `groupby` aggregation. The filter form sends one event on submission, so typing does not repeatedly run the analysis.

The full validated dataset stays in `_orders`, a backend-only state variable. Only a preview of 50 matching rows, four possible region totals, and counts are sent as frontend state. The XY chart reads those complete regional totals through `region_data`; it never sums just the 50-row preview. `cache=False` keeps this tiny chart dataset current after filtering and hydration. The download contains those complete regional totals, not just totals from the preview. Each browser session has its own uploaded records; this is not shared durable storage.

## Adapt it to your data

Replace the schema, validation, and analysis functions for your dataset. Keep the preview bounded and make clear whether a download contains raw records or aggregates. If you export user-controlled text to a spreadsheet, handle formula interpretation in your export policy.

This tutorial deliberately bounds the in-memory workload. For larger datasets, query and aggregate at the data source and use server-side pagination or a worker service. Set request-size limits at the server or proxy too: the handler's bounded read occurs after the upload reaches the endpoint. Original files are not written into the public upload directory.

To make a chart selection filter another chart and table, continue with [linked XY charts](/docs/getting-started/linked-charts-tutorial/). For saved records and access-controlled workflows, read [dashboards and internal tools](/docs/guides/dashboards-and-internal-tools/). Use [performance and execution](/docs/advanced-onboarding/performance-and-execution/) to measure parsing, filtering, and browser updates separately.
