import os

import reflex as rx

config = rx.Config(
    app_name="cluster_app",
    plugins=[rx.plugins.SitemapPlugin()],
    telemetry_enabled=False,
    **({"api_url": os.environ["CLUSTER_API_URL"]} if os.environ.get("CLUSTER_API_URL") else {}),
)
