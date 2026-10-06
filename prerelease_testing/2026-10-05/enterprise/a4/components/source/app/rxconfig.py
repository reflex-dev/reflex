"""Configure the component compatibility app and anonymous MCP endpoint."""

import os
from pathlib import Path

import reflex_enterprise as rxe
from fixture_setup import configure_fixture

configure_fixture()

config = rxe.Config(
    app_name="components",
    frontend_port=3131,
    backend_port=8131,
    api_url=os.environ.get("QA_API_URL", "http://localhost:8131"),
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    telemetry_enabled=False,
    plugins=[rxe.MCPPlugin(pending_updates="queue")],
)
