"""Configure OIDC authentication and the OAuth-protected MCP endpoint."""

from pathlib import Path

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="auth",
    frontend_port=3132,
    backend_port=8132,
    telemetry_enabled=False,
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    plugins=[
        rxe.AuthPlugin(extra_scopes=["address", "offline_access"]),
        rxe.MCPPlugin(app_scopes={"profile:read": "Read the test profile"}),
    ],
)
