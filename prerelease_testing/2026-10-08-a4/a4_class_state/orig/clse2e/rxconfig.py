import os

import reflex as rx

config = rx.Config(
    app_name="clse2e",
    disable_plugins=[rx.plugins.SitemapPlugin],
    **({"api_url": os.environ["CLSE2E_API_URL"]} if os.environ.get("CLSE2E_API_URL") else {}),
)
