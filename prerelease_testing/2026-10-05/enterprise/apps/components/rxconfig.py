"""Configure the component compatibility app and anonymous MCP endpoint."""

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="components",
    frontend_port=3131,
    backend_port=8131,
    telemetry_enabled=False,
    plugins=[rxe.MCPPlugin(pending_updates="queue")],
)
