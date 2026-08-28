"""AG Grid Demo."""

import reflex as rx

import reflex_enterprise as rxe

# from .accordion_demo import accordion_page
# from .action_icon_demo import action_icon_page
# from .alert_demo import alert_page
# from .anchor_demo import anchor_page
# from .angle_slider_demo import angle_slider_page
# from .aspect_ratio_demo import aspect_ratio_page
# from .combobox import combobox_page
from .common import DemoState, demo
from .dates import dates_page
from .pill_demo import pill_page
from .tags_input import tags_input_page

__all__ = [
    # "accordion_page",
    # "action_icon_page",
    # "alert_page",
    # "anchor_page",
    # "angle_slider_page",
    "app",
    # "combobox_page",
    # "aspect_ratio_page",
    "dates_page",
    "pill_page",
    "tags_input_page",
]


@demo(
    route="/",
    title="Mantine Demo",
    description="A collection of examples using Mantine in Reflex.",
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
# rx.Model.migrate(autogenerate=True) #
