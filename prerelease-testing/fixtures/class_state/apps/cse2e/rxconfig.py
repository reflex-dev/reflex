import os

import reflex as rx

config = rx.Config(
    app_name="cse2e",
    disable_plugins=[rx.plugins.SitemapPlugin],
    **({"api_url": os.environ["CSE2E_API_URL"]} if os.environ.get("CSE2E_API_URL") else {}),
)
