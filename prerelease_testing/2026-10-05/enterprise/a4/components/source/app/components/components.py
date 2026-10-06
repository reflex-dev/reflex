"""Exercise the public Python wrapper against real AG Grid packages."""

import inspect
import json
from typing import Any, Literal

import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.components.ag_grid.aggrid import (
    CellValueChangedEventSpec,
    FilterChangedEvent,
)
from reflex_enterprise.components.ag_grid.datasource import Datasource, SSRMDatasource
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .fly_to_location import fly_to_location
from .formatter_demo.formatters import formatter_page
from .map_controls import map_controls
from .saved_state import grid_state_serialization_advanced_page
from .vector_layers import vector_layers

__all__ = [
    "fly_to_location",
    "grid_state_serialization_advanced_page",
    "map_controls",
    "vector_layers",
]

ROWS = [
    {"id": "a", "name": "Alpha", "quantity": 3, "category": "Tools"},
    {"id": "b", "name": "Beta", "quantity": 1, "category": "Tools"},
    {"id": "c", "name": "Gamma", "quantity": 4, "category": "Parts"},
    {"id": "d", "name": "Delta", "quantity": 2, "category": "Parts"},
]


class GridState(rx.State):
    rows: list[dict[str, Any]] = ROWS
    # State-backed, nested snake_case definitions exercise formatColumnDefs in JS.
    columns: list[dict[str, Any]] = [
        {"field": "name", "pinned": "left", "filter": "agTextColumnFilter"},
        {
            "header_name": "Inventory",
            "children": [
                {
                    "field": "quantity",
                    "editable": True,
                    "cell_data_type": "number",
                    "value_formatter": "params.value + ' units'",
                },
                {"field": "category"},
            ],
        },
    ]
    selected: str = "[]"
    edit: str = "{}"
    filter_event: str = "{}"
    ready: bool = False
    theme: Literal["quartz", "alpine", "balham", "material"] = "quartz"
    query: str = ""

    @rx.event
    def grid_ready(self):
        self.ready = True

    @rx.event
    def set_theme(self, theme: str):
        if theme in ("quartz", "alpine", "balham", "material"):
            self.theme = theme

    @rx.event
    def set_query(self, query: str):
        self.query = query

    @rx.event
    def selection_changed(self, rows: list[dict], source: str, event_type: str):
        self.selected = json.dumps(sorted(row["id"] for row in rows))

    @rx.event
    def cell_changed(self, event: CellValueChangedEventSpec):
        self.edit = json.dumps(event)
        self.rows = [
            row | {event["field"]: event["newValue"]}
            if row["id"] == event["node_id"]
            else row
            for row in self.rows
        ]

    @rx.event
    def filter_changed(self, event: FilterChangedEvent):
        self.filter_event = json.dumps(event)

    @rx.event
    def replace_rows(self):
        self.rows = [{"id": "e", "name": "Echo", "quantity": 9, "category": "New"}]


class AgentState(rx.State):
    """Small state surface for anonymous MCP session isolation checks."""

    count: int = 0

    @rx.event
    def bump(self, amount: int = 1):
        """Increment the current agent session.

        Args:
            amount: Counter increment.
        """
        self.count += amount

    @rx.var
    def doubled(self) -> int:
        """Return the counter multiplied by two.

        Returns:
            Twice the current counter.
        """
        return self.count * 2

    @rxe.mcp.resource
    def summary(self, label: str) -> dict:
        """Return a parameterized read-only summary.

        Args:
            label: Label supplied through the resource URI.

        Returns:
            The label and current counter.
        """
        return {"label": label, "count": self.count}


def index(suppress_empty_overlay: bool = False) -> rx.Component:
    grid = rxe.ag_grid(
        id="inventory",
        row_data=GridState.rows,
        column_defs=GridState.columns,
        default_col_def={"width": 200, "sortable": True, "floating_filter": True},
        row_id_key="id",
        row_selection={"mode": "multiRow"},
        pagination=True,
        pagination_page_size=2,
        pagination_page_size_selector=False,
        animate_rows=False,
        pinned_top_row_data=[{"id": "pinned", "name": "Pinned", "quantity": 10}],
        quick_filter_text=GridState.query,
        suppress_overlays=["noMatchingRows"] if suppress_empty_overlay else [],
        theme=GridState.theme,
        on_grid_ready=GridState.grid_ready,
        on_selection_changed=GridState.selection_changed,
        on_cell_value_changed=GridState.cell_changed,
        on_filter_changed=GridState.filter_changed,
        width="800px",
        height="400px",
    )
    api = rxe.ag_grid.api("inventory")
    return rx.vstack(
        rx.text(rx.cond(GridState.ready, "true", "false"), id="ready"),
        rx.text(GridState.selected, id="selected"),
        rx.text(GridState.edit, id="edit"),
        rx.text(GridState.filter_event, id="filter-event"),
        rx.input(placeholder="Quick filter", on_change=GridState.set_query),
        rx.select(
            ["quartz", "alpine", "balham", "material"],
            value=GridState.theme,
            on_change=GridState.set_theme,
            id="theme",
        ),
        rx.hstack(
            rx.button("Select all", on_click=api.select_all()),
            rx.button("Deselect all", on_click=api.deselect_all()),
            rx.button("Select Beta", on_click=api.select_rows_by_key(["b"], "id")),
            rx.button("Replace rows", on_click=GridState.replace_rows),
            rx.button("Export CSV", on_click=api.export_data_as_csv()),
            rx.button(
                "Show loading",
                on_click=api.set_grid_option("loading", rx.Var.create(True)),
            ),
            rx.button(
                "Hide loading",
                on_click=api.set_grid_option("loading", rx.Var.create(False)),
            ),
        ),
        grid,
        padding="16px",
    )


def charts() -> rx.Component:
    api = rxe.ag_grid.api("charts")
    return rx.vstack(
        rx.button(
            "Create chart",
            on_click=api.create_range_chart(
                {
                    "cellRange": {"columns": ["name", "quantity"]},
                    "chartType": "groupedColumn",
                }
            ),
        ),
        rxe.ag_grid(
            id="charts",
            row_data=ROWS,
            column_defs=[
                rxe.ag_grid.column_def(field="name", chart_data_type="category"),
                rxe.ag_grid.column_def(field="quantity", chart_data_type="series"),
            ],
            enable_charts=True,
            cell_selection=True,
            width="800px",
            height="400px",
        ),
    )


def grouping() -> rx.Component:
    return rxe.ag_grid(
        id="groups",
        row_data=ROWS,
        column_defs=[
            {"field": "category", "row_group": True, "hide": True},
            {"field": "name"},
            {"field": "quantity", "agg_func": "sum"},
        ],
        auto_group_column_def={"headerName": "Category", "minWidth": 250},
        group_default_expanded=0,
        width="800px",
        height="400px",
    )


async def rows_endpoint(request: Request) -> JSONResponse:
    params = request.query_params
    rows = ROWS
    for sort in reversed(json.loads(params.get("sortModel", "[]"))):
        rows = sorted(
            rows, key=lambda row: row[sort["colId"]], reverse=sort["sort"] == "desc"
        )
    start, end = int(params["startRow"]), int(params["endRow"])
    if request.path_params["model"] == "serverSide":
        return JSONResponse({"rowData": rows[start:end], "rowCount": len(rows)})
    return JSONResponse([rows[start:end], len(rows)])


def remote_grid(model: str) -> rx.Component:
    datasource_type = SSRMDatasource if model == "serverSide" else Datasource
    datasource_prop = (
        "server_side_datasource" if model == "serverSide" else "datasource"
    )
    datasource_props: dict[str, Any] = {
        datasource_prop: datasource_type(endpoint_uri=f"/grid-rows/{model}")
    }
    return rxe.ag_grid(
        id="remote",
        row_model_type=model,
        column_defs=[{"field": "name"}, {"field": "quantity"}],
        default_col_def={"sortable": True},
        cache_block_size=2,
        animate_rows=False,
        pagination=True,
        pagination_page_size=2,
        pagination_page_size_selector=False,
        width="800px",
        height="400px",
        **datasource_props,
    )


app = rxe.App(
    api_transformer=Starlette(routes=[Route("/grid-rows/{model}", rows_endpoint)]),
    head_components=rxe.google_font("Inter", weights=[400, 700]),
)
app.add_page(index)
app.add_page(lambda: index(True), route="/suppress-overlay")
app.add_page(charts, route="/charts")
app.add_page(grouping, route="/grouping")
app.add_page(lambda: remote_grid("infinite"), route="/infinite")
app.add_page(lambda: remote_grid("serverSide"), route="/server-side")

app.add_page(inspect.unwrap(formatter_page), route="/formatters-direct")
