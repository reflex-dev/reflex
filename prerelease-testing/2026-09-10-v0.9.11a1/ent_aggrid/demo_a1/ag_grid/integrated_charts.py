"""Example of handling grid selection events and displaying selected items in a separate panel."""

import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

from .common import demo

df = pd.read_csv(
    "https://raw.githubusercontent.com/plotly/datasets/master/wind_dataset.csv"
)

column_defs = [
    rxe.ag_grid.column_def(field="direction"),  # pyright: ignore [reportCallIssue]
    rxe.ag_grid.column_def(field="strength"),  # pyright: ignore [reportCallIssue]
    rxe.ag_grid.column_def(field="frequency"),  # pyright: ignore [reportCallIssue]
]


@demo(
    route="/integrated-charts",
    title="Integrated Charts",
    description="Select a range of data, then right-click to create a chart.",
)
def integrated_chart_page():
    """Selected items example."""
    return rx.hstack(
        rxe.ag_grid(
            id="ag_grid_integrated_charts",
            column_defs=column_defs,  # pyright: ignore [reportArgumentType]
            row_data=df.to_dict("records"),  # pyright: ignore [reportArgumentType]
            width="100%",
            height="71vh",
            enable_charts=True,
            cell_selection=True,
            enterprise_modules={"AllEnterpriseModule"},
        ),
        width="100%",
    )
