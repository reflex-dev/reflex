import reflex as rx
from reflex.page import DECORATED_PAGES

import flow.add_nodes_on_edge_drop
import flow.connection_limit
import flow.custom_node
import flow.drag_handle
import flow.intersections
import flow.overview  # noqa: F401
import reflex_enterprise as rxe

app = rxe.App(
    stylesheets=["xy-theme.css", "style.css"],
    theme=rx.theme(appearance="light"),
)

pages = {
    page["title"]: page["route"]
    for _, page in next(DECORATED_PAGES.values().__iter__())
}
app.add_page(
    lambda: rx.vstack(*[rx.link(title, href=route) for title, route in pages.items()]),
    route="/",
)
