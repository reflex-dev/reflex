"""AG Grid Demo."""

import reflex as rx

import reflex_enterprise as rxe

from .aligned_grids import aligned_grids_page
from .cell_selection import cell_selection_page
from .common import DemoState, demo
from .editable import editable_page
from .fill_handle import fill_handle_page
from .formatters import formatter_page
from .grid_state_serialization import grid_state_serialization_simple_page
from .grid_state_serialization_advanced import grid_state_serialization_advanced_page
from .integrated_charts import integrated_chart_page
from .master_detail import master_detail_page
from .model_wrapper_customized import model_page_auth
from .model_wrapper_simple import model_page
from .model_wrapper_ssrm import model_page_ssrm
from .pivot import pivot_page
from .selected_items import selected_items_example
from .state_grid import state_grid_page
from .tree import tree_example

__all__ = [
    "aligned_grids_page",
    "app",
    "cell_selection_page",
    "editable_page",
    "fill_handle_page",
    "formatter_page",
    "grid_state_serialization_advanced_page",
    "grid_state_serialization_simple_page",
    "integrated_chart_page",
    "master_detail_page",
    "model_page",
    "model_page_auth",
    "model_page_ssrm",
    "pivot_page",
    "selected_items_example",
    "state_grid_page",
    "tree_example",
]


@demo(
    route="/",
    title="AG Grid Demo",
    description="A collection of examples using AG Grid in Reflex.",
)
def index():
    """Index page for the AG Grid demos."""
    return rx.flex(
        rx.foreach(
            DemoState.pages,
            lambda page: rx.card(
                rx.vstack(
                    rx.link(page.title, href=page.route),
                    rx.text(page.description),
                ),
                width="300px",
            ),
        ),
        wrap="wrap",
        spacing="3",
    )


# Add state and page to the app.
app = rxe.App()

# Uncomment this when deploying demos, to initialize the database.
# rx.utils.prerequisites.check_db_initialized() or rx.Model.alembic_init()
# rx.Model.migrate(autogenerate=True)
