import os

import reflex as rx

_port = os.environ.get("VERIFY_BACKEND_PORT", "8680")

config = rx.Config(
    app_name="corev",
    api_url=f"http://localhost:{_port}",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
