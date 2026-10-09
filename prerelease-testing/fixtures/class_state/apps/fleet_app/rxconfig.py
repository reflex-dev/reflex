import os

import reflex as rx

config = rx.Config(
    app_name="fleet",
    plugins=[rx.plugins.SitemapPlugin()] if hasattr(rx, "plugins") else [],
    **({"api_url": os.environ["FLEET_API_URL"]} if os.environ.get("FLEET_API_URL") else {}),
)
