"""Configure the component compatibility app and anonymous MCP endpoint (ent_auth ports; no custom bun_path)."""

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="components",
    frontend_port=3346,
    backend_port=8346,
    telemetry_enabled=False,
    plugins=[rxe.MCPPlugin(pending_updates="queue")],
)
