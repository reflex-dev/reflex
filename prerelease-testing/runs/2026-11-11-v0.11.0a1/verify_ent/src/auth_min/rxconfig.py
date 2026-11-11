"""Configure the local OIDC provider and protected MCP endpoint."""

import os
from pathlib import Path

import reflex as rx

assert os.environ.get("VE_VENV", "<unset>") in rx.__file__, rx.__file__

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="auth_min",
    frontend_port=3880,
    backend_port=8880,
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
