import os

import reflex as rx

config = rx.Config(
    app_name="dynhook",
    disable_plugins=[rx.plugins.SitemapPlugin],
    **({"api_url": os.environ["DH_API_URL"]} if os.environ.get("DH_API_URL") else {}),
)
