import reflex as rx

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

# PATCHED FOR 0.9.9a1 TESTING (ent_misc cluster):
# original line `from reflex.page import DECORATED_PAGES` raises
#   ImportError: cannot import name 'DECORATED_PAGES' from 'PageNamespace' (unknown location)
# on reflex 0.9.9a1 (DECORATED_PAGES removed; pages now live on the active
# RegistrationContext). Fallback below only to keep exercising the rest of the demo.
try:
    from reflex.page import DECORATED_PAGES  # pyright: ignore[reportAttributeAccessIssue]

    _pages_iter = next(DECORATED_PAGES.values().__iter__())
except ImportError:
    from reflex_base.registry import RegistrationContext

    _pages_iter = RegistrationContext.ensure_context().decorated_pages

pages = {page["title"]: page["route"] for _, page in _pages_iter}
app.add_page(
    lambda: rx.vstack(*[rx.link(title, href=route) for title, route in pages.items()]),
    route="/",
)
