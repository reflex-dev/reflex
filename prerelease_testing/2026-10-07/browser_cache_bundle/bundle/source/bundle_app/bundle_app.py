"""Same modular multipage app for all published release trains."""

import reflex as rx
from .common import VERSION
from .dashboard import dashboard
from .editor import editor
from .home import index
from .reports import reports

print("BUNDLE_APP", VERSION, rx.__file__, flush=True)
app = rx.App(theme=rx.theme(appearance="light"))
app.add_page(index, route="/")
app.add_page(dashboard, route="/dashboard")
app.add_page(reports, route="/reports")
app.add_page(editor, route="/editor")
