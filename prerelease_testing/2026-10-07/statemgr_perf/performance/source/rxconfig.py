"""Memory-state production comparison without storage I/O in the event path."""

import os
import reflex as rx

config = rx.Config(
    app_name="perf_app",
    telemetry_enabled=False,
    state_manager_mode="memory",
    api_url=os.environ.get("PERF_API_URL", "http://localhost:8274"),
    plugins=[rx.plugins.SitemapPlugin()],
)
