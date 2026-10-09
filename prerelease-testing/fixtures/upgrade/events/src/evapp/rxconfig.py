"""Config for the events_vars cluster app; ports come from the environment."""

import os

import reflex as rx
from reflex.plugins.sitemap import SitemapPlugin

_fp = int(os.environ.get("EV_FP", "3460"))
_bp = int(os.environ.get("EV_BP", "8460"))

config = rx.Config(
    app_name="evapp",
    frontend_port=_fp,
    backend_port=_bp,
    api_url=os.environ.get("EV_API_URL", f"http://localhost:{_bp}"),
    telemetry_enabled=False,
    disable_plugins=[SitemapPlugin],
)
