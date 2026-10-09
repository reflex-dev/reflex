import os

import reflex as rx

config = rx.Config(
    app_name="lateapp",
    disable_plugins=[rx.plugins.SitemapPlugin],
    **({"api_url": os.environ["LATE_API_URL"]} if os.environ.get("LATE_API_URL") else {}),
)
