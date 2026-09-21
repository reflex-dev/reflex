---
title: Build a Pandas Data App with Reflex
meta_description: Turn pandas analysis into a Python web app. Upload a CSV, filter records, aggregate by region, preview rows, and download the filtered summary with Reflex.
---

# Build a pandas data app

Use Reflex to put a custom web interface around pandas analysis. This example uploads a CSV, filters its records, groups units by region, and downloads the filtered summary. The parsing and analysis functions remain ordinary Python functions; Reflex connects them to file input, a filter form, and result tables.

The app runs locally without a database or API key. It includes sample data, so you can try the complete analysis flow before uploading a file. Uploads run in your own app; this documentation site does not accept files.

## Set up the app

Create a blank app using the [installation guide](/docs/getting-started/installation/), then install pandas:

```bash
uv add pandas
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

```python id=pandas_data_app
import asyncio
import warnings
from io import BytesIO
from typing import Any, TypedDict

import pandas as pd
import reflex as rx


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


def read_orders(data: bytes) -> list[OrderRow]:
    """Parse a bounded CSV and validate its columns and record values."""
    if len(data) > MAX_CSV_BYTES:
        raise ValueError("Choose a CSV of at most 2 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", pd.errors.ParserWarning)
            frame = pd.read_csv(
                BytesIO(data),
                encoding="utf-8-sig",
                dtype=str,
                keep_default_na=False,
                index_col=False,
                nrows=MAX_ROWS + 1,
            )
    except (
        UnicodeDecodeError,
        pd.errors.ParserError,
        pd.errors.ParserWarning,
    ) as error:
        raise ValueError(
            "Choose a valid UTF-8 CSV with three columns per row."
        ) from error
    except pd.errors.EmptyDataError as error:
        raise ValueError("The CSV needs a header and at least one record.") from error
    if list(frame.columns) != ["region", "product", "units"]:
        raise ValueError("Use exactly these columns: region,product,units.")
    if not 1 <= len(frame) <= MAX_ROWS:
        raise ValueError("Include between 1 and 10,000 records.")
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
    def load_sample(self):
        """Replace the dataset while retaining the applied filter."""
        if self.processing:
            return
        self._orders = read_orders(SAMPLE_CSV)
        self.error = ""
        self._refresh()
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


def pandas_data_app():
    """Render dataset controls, filters, summary, and a bounded record preview."""
    return rx.vstack(
        rx.heading("Order explorer", size="6"),
        rx.text(
            "Upload orders, filter products, and summarize units by region.", size="2"
        ),
        rx.button(
            "Use sample data",
            on_click=PandasAppState.load_sample,
            disabled=PandasAppState.processing,
            variant="soft",
        ),
        rx.upload(
            rx.vstack(
                rx.text("Drop a CSV here or choose a file", weight="medium"),
                rx.text("UTF-8 · up to 2 MiB · 10,000 rows", size="2"),
                rx.foreach(rx.selected_files(UPLOAD_ID), lambda name: rx.text(name)),
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
            on_click=PandasAppState.upload_csv(rx.upload_files(upload_id=UPLOAD_ID)),
            loading=PandasAppState.processing,
            disabled=rx.selected_files(UPLOAD_ID).length() == 0,
        ),
        rx.cond(
            PandasAppState.error != "",
            rx.text(PandasAppState.error, role="alert", color=rx.color("red", 11)),
        ),
        rx.form(
            rx.grid(
                rx.vstack(
                    rx.el.label("Region", html_for="order-region"),
                    rx.el.select(
                        *[
                            rx.el.option(value, value=value)
                            for value in ["All", *REGIONS]
                        ],
                        id="order-region",
                        name="region",
                        default_value="All",
                        disabled=PandasAppState.processing,
                        padding="0.6rem",
                        border=f"1px solid {rx.color('gray', 7)}",
                        border_radius="6px",
                        background=rx.color("gray", 1),
                    ),
                    align_items="stretch",
                    spacing="2",
                ),
                rx.vstack(
                    rx.el.label("Product contains", html_for="order-product"),
                    rx.input(
                        id="order-product",
                        name="product",
                        placeholder="e.g. Tea",
                        size="3",
                        max_length=80,
                        disabled=PandasAppState.processing,
                    ),
                    align_items="stretch",
                    spacing="2",
                ),
                rx.button(
                    "Apply filters",
                    type="submit",
                    size="3",
                    align_self="end",
                    disabled=PandasAppState.processing,
                ),
                columns={"initial": "1", "md": "3"},
                spacing="3",
                width="100%",
            ),
            on_submit=PandasAppState.apply_filters,
            width="100%",
        ),
        rx.text(
            PandasAppState.matching_count,
            " matching records · ",
            PandasAppState.total_units,
            " units · ",
            PandasAppState.loaded_count,
            " records loaded",
            role="status",
            size="2",
        ),
        rx.heading("Units by region", size="4", as_="h2"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Region"),
                    rx.table.column_header_cell("Units"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    PandasAppState.summary,
                    lambda row: rx.table.row(
                        rx.table.cell(row["region"]),
                        rx.table.cell(row["units"]),
                    ),
                )
            ),
            width="100%",
        ),
        rx.button(
            "Download summary",
            on_click=PandasAppState.download_summary,
            disabled=PandasAppState.processing | (PandasAppState.matching_count == 0),
            variant="soft",
        ),
        rx.heading("Matching orders", size="4", as_="h2"),
        rx.text("Showing the first 50 matches. Totals include all matches.", size="2"),
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(*[
                        rx.table.column_header_cell(label)
                        for label in ["Region", "Product", "Units"]
                    ])
                ),
                rx.table.body(
                    rx.foreach(
                        PandasAppState.rows,
                        lambda row: rx.table.row(
                            rx.table.cell(row["region"]),
                            rx.table.cell(row["product"]),
                            rx.table.cell(row["units"]),
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
            rx.text("No matching records. Load data or change the filters.", size="2"),
        ),
        spacing="4",
        align_items="stretch",
        width="100%",
        max_width="48rem",
        margin="2rem auto",
        padding=["1rem", "1.5rem"],
        border=f"1px solid {rx.color('gray', 5)}",
        border_radius="12px",
    )
```

Register the page at the app root:

```python
app = rx.App()
app.add_page(pandas_data_app, route="/")
```

Run `uv run reflex run`. Select **Use sample data**: four records total 33 units. Filter for North and Tea: one record totals 12 units. Download the summary to get `North,12`. A search with no matches clears both result tables and disables download. Uploading an invalid CSV clears the previous dataset and shows an error; a valid upload or the sample button lets you recover.

## Where pandas runs

`read_orders` parses and validates the upload on the backend. Parsing runs in a worker thread; the upload handler shows progress before awaiting it. `analyze_orders` uses a pandas DataFrame for literal text filtering and `groupby` aggregation. The filter form sends one event on submission, so typing does not repeatedly run the analysis.

The full validated dataset stays in `_orders`, a backend-only state variable. Only a preview of 50 matching rows, four possible region totals, and counts are sent as frontend state. The download contains those complete regional totals, not just totals from the preview. Each browser session has its own uploaded records; this is not shared durable storage.

## Adapt it to your data

Replace the schema, validation, and analysis functions for your dataset. Keep the preview bounded and make clear whether a download contains raw records or aggregates. If you export user-controlled text to a spreadsheet, handle formula interpretation in your export policy.

This tutorial deliberately bounds the in-memory workload. For larger datasets, query and aggregate at the data source and use server-side pagination or a worker service. Set request-size limits at the server or proxy too: the handler's bounded read occurs after the upload reaches the endpoint. Original files are not written into the public upload directory.

To connect the results to charts, continue with [linked XY charts](/docs/getting-started/linked-charts-tutorial/). For saved records and access-controlled workflows, read [dashboards and internal tools](/docs/guides/dashboards-and-internal-tools/). Use [performance and execution](/docs/advanced-onboarding/performance-and-execution/) to measure parsing, filtering, and browser updates separately.
