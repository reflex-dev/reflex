import os

import reflex as rx

config = rx.Config(
    app_name="core_a2",
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
    **({"api_url": os.environ["CORE_API_URL"]} if os.environ.get("CORE_API_URL") else {}),
)
