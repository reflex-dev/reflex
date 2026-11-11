"""Config for the N-024 docs-claim app; ports come from the environment (bin/start.sh)."""

import os

import reflex as rx
from reflex.plugins.sitemap import SitemapPlugin

_fp = int(os.environ.get("EV_FP", "3474"))
_bp = int(os.environ.get("EV_BP", "8474"))

config = rx.Config(
    app_name="n024doc",
    frontend_port=_fp,
    backend_port=_bp,
    api_url=os.environ.get("EV_API_URL", f"http://localhost:{_bp}"),
    telemetry_enabled=False,
    disable_plugins=[SitemapPlugin],
)
