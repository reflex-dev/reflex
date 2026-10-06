"""Configure the local production MCP comparison."""

from pathlib import Path

import reflex_enterprise as rxe
from fixture_setup import configure_fixture

configure_fixture()

config = rxe.Config(
    app_name="mcp_probe",
    frontend_port=3131,
    backend_port=3131,
    api_url="http://localhost:3131",
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    telemetry_enabled=False,
    plugins=[rxe.MCPPlugin()],
)
