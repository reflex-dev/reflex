"""Minimal reflex-enterprise ag-grid app.

Two variants controlled by env var REPRO_LAMBDA:
- unset (default): a single plain rxe.ag_grid (no lambda props). Expected to
  compile and run on both reflex 0.9.8 and 0.9.9a1.
- REPRO_LAMBDA=1: adds one column whose cell_renderer is a python lambda that
  returns an rx.text component. LiteralLambdaVar validation then reads
  reflex.components.dynamic.bundled_libraries, which reflex 0.9.9a1 removed
  (breaking change #6382) -> AttributeError, surfaced (masked) as
  VarAttributeError: Attribute _cached_get_all_var_data not found.
"""

import os

import reflex as rx

import reflex_enterprise as rxe

row_data = [
    {"name": "John", "age": 30},
    {"name": "Anna", "age": 25},
    {"name": "Mike", "age": 35},
]

column_defs: list[dict] = [
    {"field": "name"},
    {"field": "age"},
]

if os.environ.get("REPRO_LAMBDA"):
    column_defs.append(
        {
            "field": "fancy",
            "value_getter": "params.data.name",
            # python lambda cell_renderer returning a component => LiteralLambdaVar
            # whose return expr carries imports => triggers the bundled_libraries
            # read in reflex_enterprise/vars.py:143.
            "cell_renderer": lambda params: rx.text(params.value, color="tomato"),
        }
    )


def index() -> rx.Component:
    """Single page with one grid."""
    return rx.container(
        rx.heading("minimal rxe.ag_grid", id="title"),
        rxe.ag_grid(
            id="mingrid",
            row_data=row_data,
            column_defs=column_defs,
            width="90vw",
            height="60vh",
        ),
    )


app = rxe.App()
app.add_page(index, route="/")
