"""Configure isolated OIDC and OAuth-protected MCP security probes."""

from pathlib import Path

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="security_probe",
    frontend_port=3152,
    backend_port=8152,
    telemetry_enabled=False,
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    plugins=[
        rxe.AuthPlugin(extra_scopes=["offline_access"]),
        rxe.MCPPlugin(app_scopes={"profile:read": "Read the security probe profile"}),
    ],
)
