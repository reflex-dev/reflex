import os

import reflex as rx

config = rx.Config(
    app_name="c4e2e",
    disable_plugins=[rx.plugins.SitemapPlugin],
    **({"api_url": os.environ["C4_API_URL"]} if os.environ.get("C4_API_URL") else {}),
)
