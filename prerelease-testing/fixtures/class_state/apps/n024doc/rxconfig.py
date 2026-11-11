"""Config for the N-024 / A3-06 docs-claim app. Ports come from `reflex run --frontend-port/--backend-port` (bin/start_app.sh);
for prod on one port set N024_API_URL=http://localhost:<port>."""

import os

import reflex as rx
from reflex.plugins.sitemap import SitemapPlugin

config = rx.Config(
    app_name="n024doc",
    telemetry_enabled=False,
    disable_plugins=[SitemapPlugin],
    **({"api_url": os.environ["N024_API_URL"]} if os.environ.get("N024_API_URL") else {}),
)
