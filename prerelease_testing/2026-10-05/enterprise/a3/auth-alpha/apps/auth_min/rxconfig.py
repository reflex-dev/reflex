"""Configure the local OIDC provider and protected MCP endpoint."""

import os
from pathlib import Path

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="auth_min",
    frontend_port=3132,
    backend_port=8132,
    telemetry_enabled=False,
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    plugins=[
        rxe.AuthPlugin(
            extra_scopes=["offline_access"]
            if os.environ.get("AUTH_TEST_EXTRA_SCOPES")
            else []
        ),
        rxe.MCPPlugin(app_scopes={"profile:read": "Read the test profile"}),
    ],
)
