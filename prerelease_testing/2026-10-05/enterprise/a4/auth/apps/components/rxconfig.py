"""Configure the component compatibility app and anonymous MCP endpoint."""

from pathlib import Path

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="components",
    backend_port=8132,
    telemetry_enabled=False,
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    plugins=[rxe.MCPPlugin(pending_updates="queue")],
)
