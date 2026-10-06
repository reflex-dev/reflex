"""Configure a local browser-only cookie validation app."""

from pathlib import Path

import reflex as rx

config = rx.Config(
    app_name="cookie_app",
    frontend_port=3145,
    backend_port=8145,
    telemetry_enabled=False,
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    plugins=[rx.plugins.RadixThemesPlugin()],
)
