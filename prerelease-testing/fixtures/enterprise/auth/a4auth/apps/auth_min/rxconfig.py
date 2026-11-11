"""Configure the local OIDC provider and protected MCP endpoint."""

import os
from pathlib import Path

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="auth_min",
    frontend_port=3623,
    backend_port=8623,
    telemetry_enabled=False,
    plugins=[
        rxe.AuthPlugin(
            extra_scopes=["offline_access"]
            if os.environ.get("AUTH_TEST_EXTRA_SCOPES")
            else []
        ),
        rxe.MCPPlugin(app_scopes={"profile:read": "Read the test profile"}),
    ],
)
