"""Probe each ag_grid demo page: build its component tree and emulate the
plugin compiler's visit (children + _get_components_in_props) to find which
page/prop crashes on reflex 0.9.9a1. Run from inside a demo copy dir."""

import sys
import traceback

import reflex as rx
from reflex.components.component import Component

from ag_grid import ag_grid as demo_module  # noqa: F401  (registers pages)
from ag_grid.aligned_grids import aligned_grids_page
from ag_grid.cell_selection import cell_selection_page
from ag_grid.editable import editable_page
from ag_grid.fill_handle import fill_handle_page
from ag_grid.formatters import formatter_page
from ag_grid.grid_state_serialization import grid_state_serialization_simple_page
from ag_grid.grid_state_serialization_advanced import (
    grid_state_serialization_advanced_page,
)
from ag_grid.integrated_charts import integrated_chart_page
from ag_grid.master_detail import master_detail_page
from ag_grid.model_wrapper_customized import model_page_auth
from ag_grid.model_wrapper_simple import model_page
from ag_grid.model_wrapper_ssrm import model_page_ssrm
from ag_grid.pivot import pivot_page
from ag_grid.selected_items import selected_items_example
from ag_grid.state_grid import state_grid_page
from ag_grid.tree import tree_example

PAGES = {
    "aligned_grids": aligned_grids_page,
    "cell_selection": cell_selection_page,
    "editable": editable_page,
    "fill_handle": fill_handle_page,
    "formatters": formatter_page,
    "grid_state_serialization": grid_state_serialization_simple_page,
    "grid_state_serialization_advanced": grid_state_serialization_advanced_page,
    "integrated_charts": integrated_chart_page,
    "master_detail": master_detail_page,
    "model_wrapper_customized": model_page_auth,
    "model_wrapper_simple": model_page,
    "model_wrapper_ssrm": model_page_ssrm,
    "pivot": pivot_page,
    "selected_items": selected_items_example,
    "state_grid": state_grid_page,
    "tree": tree_example,
}


def visit(comp, path):
    """Recursively visit a component like the plugin compiler does."""
    if not isinstance(comp, Component):
        return
    label = f"{path}/{type(comp).__name__}"
    for prop_component in comp._get_components_in_props():
        visit(prop_component, label + "[prop]")
    for child in comp.children:
        visit(child, label)


results = {}
for name, page_fn in PAGES.items():
    try:
        comp = page_fn()
        visit(comp, name)
        results[name] = "OK"
        print(f"PASS  {name}")
    except Exception as e:
        results[name] = f"FAIL: {type(e).__name__}: {e}"
        print(f"FAIL  {name}: {type(e).__name__}: {e}")
        if "-v" in sys.argv:
            traceback.print_exc()

print("\nSummary:")
for name, res in results.items():
    print(f"  {name}: {res}")
