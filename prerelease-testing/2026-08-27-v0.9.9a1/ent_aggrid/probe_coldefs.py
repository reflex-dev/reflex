"""Narrow the formatters-page crash to a single column def / var.

Run from a demo copy dir with PYTHONPATH pointing at it.
"""

import traceback

import reflex as rx
from reflex.components.component import Component

from ag_grid.formatters import cols_defs, data_dialog, row_data

import reflex_enterprise as rxe


def visit(comp):
    """Emulate the plugin compiler's tree walk."""
    if not isinstance(comp, Component):
        return
    for prop_component in comp._get_components_in_props():
        visit(prop_component)
    for child in comp.children:
        visit(child)


for i, col in enumerate(cols_defs):
    grid = rxe.ag_grid(
        id=f"g{i}",
        column_defs=[col],
        row_data=row_data,
        components={"dataDialog": data_dialog},
    )
    try:
        visit(grid)
        print(f"PASS col[{i}] field={col.get('field')}")
    except Exception as e:
        print(f"FAIL col[{i}] field={col.get('field')}: {type(e).__name__}: {e}")

print("\nnow narrow inside the failing col: probe each key variant")
import copy

for i, col in enumerate(cols_defs):
    for key in ("value_getter", "value_formatter", "cell_renderer"):
        if key not in col:
            continue
        solo = {"field": col["field"], key: col[key]}
        grid = rxe.ag_grid(id=f"g{i}{key}", column_defs=[solo], row_data=row_data)
        try:
            visit(grid)
            print(f"PASS col[{i}].{key} ({col.get('field')})")
        except Exception as e:
            print(
                f"FAIL col[{i}].{key} ({col.get('field')}): {type(e).__name__}: {e}"
            )
            traceback.print_exc()
