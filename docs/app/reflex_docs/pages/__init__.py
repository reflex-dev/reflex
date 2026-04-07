from reflex_ui_shared.gallery.apps import gallery_apps_routes
from reflex_ui_shared.pages.page404 import page404  # noqa: F401
from reflex_ui_shared.route import Route

from reflex_docs.pages.docs import doc_routes
from reflex_docs.pages.docs_landing import docs_landing  # noqa: F401

routes = [
    *[r for r in locals().values() if isinstance(r, Route) and r.add_as_page],
    *doc_routes,
    *gallery_apps_routes,
]
