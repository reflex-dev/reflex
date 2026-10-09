"""Anonymous MCP app for a4auth/check_mcp.py (backend only, port 8626; no frontend_port: --backend-only refuses a configured one)."""

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="components",
    backend_port=8626,
    telemetry_enabled=False,
    plugins=[rxe.MCPPlugin(pending_updates="queue")],
)
