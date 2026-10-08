import os

import reflex as rx

config = rx.Config(app_name="badassign", disable_plugins=[rx.plugins.SitemapPlugin],
                   **({"api_url": os.environ["BA_API_URL"]} if os.environ.get("BA_API_URL") else {}))
