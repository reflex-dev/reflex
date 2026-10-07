import os

import reflex as rx

config = rx.Config(
    app_name="stor",
    plugins=[rx.plugins.SitemapPlugin()],
    **({"api_url": os.environ["STOR_API_URL"]} if os.environ.get("STOR_API_URL") else {}),
)
