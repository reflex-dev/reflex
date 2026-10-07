"""Configure OIDC authentication and the OAuth-protected MCP endpoint."""

from pathlib import Path

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="auth",
    frontend_port=3342,
    backend_port=8342,
    telemetry_enabled=False,
    plugins=[
        rxe.AuthPlugin(extra_scopes=["address", "offline_access"]),
        rxe.MCPPlugin(app_scopes={"profile:read": "Read the test profile"}),
    ],
)
