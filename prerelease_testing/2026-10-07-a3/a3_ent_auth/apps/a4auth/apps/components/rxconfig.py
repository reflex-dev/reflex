"""Configure the component compatibility app and anonymous MCP endpoint (ent_auth backend port 8346; no custom bun_path; no frontend_port: --backend-only refuses a configured frontend_port on 0.9.12 and 0.10)."""

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="components",
    backend_port=8346,
    telemetry_enabled=False,
    plugins=[rxe.MCPPlugin(pending_updates="queue")],
)
