"""Cloud review demo on its own ports, without telemetry or a database."""

import reflex as rx
import reflex_xy

config = rx.Config(
    app_name="session_demo",
    telemetry_enabled=False,
    state_manager_mode=rx.constants.StateManagerMode.MEMORY,
    frontend_port=4201,
    backend_port=8201,
    plugins=[rx.plugins.TailwindV4Plugin(), reflex_xy.XYPlugin()],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
