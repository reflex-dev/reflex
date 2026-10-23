import os

import reflex as rx

config = rx.Config(
    app_name="schemaapp",
    # The prod frontend is served separately from the backend in these tests,
    # so the backend URL is pinned instead of derived from --backend-port.
    api_url=os.environ.get("SCHEMA_API_URL", "http://localhost:8221"),
    plugins=[rx.plugins.RadixThemesPlugin()],
)
