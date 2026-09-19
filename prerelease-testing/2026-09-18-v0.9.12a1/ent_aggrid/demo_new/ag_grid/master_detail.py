"""Master Detail Demo for AG Grid."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo

# Static column definitions (non-Var)
STATIC_COLUMN_DEFS = [
    {
        "field": "id",
        "header_name": "ID",
        "width": 80,
        "cell_renderer": "agGroupCellRenderer",
    },
    {"field": "name", "header_name": "Product Name", "width": 150},
    {"field": "category", "header_name": "Category", "width": 120},
    {
        "field": "price",
        "header_name": "Price",
        "width": 100,
        "value_formatter": "params.value ? '$' + params.value.toFixed(2) : ''",
    },
]

# Static detail cell renderer params (non-Var)
STATIC_DETAIL_PARAMS = {
    "detail_grid_options": {
        "column_defs": [
            {"field": "count", "header_name": "Count"},
            {"field": "value", "header_name": "Description"},
        ]
    },
    "get_detail_row_data": lambda params: rx.vars.function.FunctionStringVar(
        "params.successCallback"
    ).call(params.data.counts),
}


class MasterDetailState(rx.State):
    """State for the master detail demo."""

    # Sample data with nested detail information
    master_data: list[dict] = [
        {
            "id": 1,
            "name": "Product A",
            "category": "Electronics",
            "price": 299.99,
            "counts": [
                {"count": 10, "value": "Stock Level"},
                {"count": 5, "value": "Orders Today"},
                {"count": 25, "value": "Total Sales"},
            ],
        },
        {
            "id": 2,
            "name": "Product B",
            "category": "Clothing",
            "price": 49.99,
            "counts": [
                {"count": 50, "value": "Stock Level"},
                {"count": 12, "value": "Orders Today"},
                {"count": 78, "value": "Total Sales"},
            ],
        },
        {
            "id": 3,
            "name": "Product C",
            "category": "Books",
            "price": 19.99,
            "counts": [
                {"count": 30, "value": "Stock Level"},
                {"count": 8, "value": "Orders Today"},
                {"count": 45, "value": "Total Sales"},
            ],
        },
        {
            "id": 4,
            "name": "Product D",
            "category": "Home & Kitchen",
            "price": 89.99,
            "counts": [
                {"count": 20, "value": "Stock Level"},
                {"count": 3, "value": "Orders Today"},
                {"count": 15, "value": "Total Sales"},
            ],
        },
    ]

    # Assign static definitions to State vars to test Var handling
    column_defs: list[dict] = STATIC_COLUMN_DEFS
    detail_cell_renderer_params: dict = STATIC_DETAIL_PARAMS


@demo(
    route="/master-detail",
    title="Master Detail",
    description="Demonstrates AG Grid master detail functionality with expandable rows showing detailed information.",
)
def master_detail_page():
    """Master detail demo page."""
    return rx.vstack(
        rx.heading("Master Detail Demo", size="6"),
        rx.text(
            "Click the expand icon (►) on any row to see detailed information in a nested grid below."
        ),
        rx.text(
            "Both grids should behave identically - one uses State Vars (left) and one uses static objects (right).",
            size="2",
            color="gray",
        ),
        # Two grids side by side
        rx.hstack(
            # State Vars grid (left)
            rx.vstack(
                rx.heading("State Vars (Dynamic)", size="4", color="green"),
                rx.text("Using column_defs and detail params from State", size="2"),
                rxe.ag_grid(
                    id="state-vars-grid",
                    row_data=MasterDetailState.master_data,
                    column_defs=MasterDetailState.column_defs,
                    master_detail=True,
                    detail_cell_renderer_params=MasterDetailState.detail_cell_renderer_params,
                    height="400px",
                    width="100%",
                ),
                width="50%",
                spacing="2",
            ),
            # Static objects grid (right)
            rx.vstack(
                rx.heading("Static Objects", size="4", color="blue"),
                rx.text("Using static column definitions and detail params", size="2"),
                rxe.ag_grid(
                    id="static-objects-grid",
                    row_data=MasterDetailState.master_data,
                    column_defs=STATIC_COLUMN_DEFS,
                    master_detail=True,
                    detail_cell_renderer_params=STATIC_DETAIL_PARAMS,
                    height="400px",
                    width="100%",
                ),
                width="50%",
                spacing="2",
            ),
            spacing="4",
            width="100%",
        ),
        spacing="4",
        width="100%",
        padding="4",
    )
