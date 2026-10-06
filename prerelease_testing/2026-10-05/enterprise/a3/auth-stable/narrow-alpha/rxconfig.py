"""Configure the isolated OIDC reproduction with an existing Bun binary."""

from pathlib import Path

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="reload_probe",
    frontend_port=3152,
    backend_port=8152,
    telemetry_enabled=False,
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    plugins=[rxe.AuthPlugin(extra_scopes=["offline_access"])],
)
