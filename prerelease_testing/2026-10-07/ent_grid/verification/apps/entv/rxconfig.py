import os

import reflex_enterprise as rxe

_port = os.environ.get("VERIFY_BACKEND_PORT", "8680")

config = rxe.Config(
    app_name="entv",
    api_url=f"http://localhost:{_port}",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
)
