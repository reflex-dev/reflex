"""Production configuration for the bundle/cache comparison."""

import os
import reflex as rx

config = rx.Config(
    app_name="bundle_app",
    telemetry_enabled=False,
    api_url=os.environ["BUNDLE_API_URL"],
    frontend_lazy_bundled_libraries=os.environ.get("BUNDLE_LAZY", "0") == "1",
    plugins=[rx.plugins.SitemapPlugin()],
)
