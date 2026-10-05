"""Configure a local badge-policy app with temporary account credentials."""

import os
from pathlib import Path

import reflex_enterprise as rxe
from fixture_setup import configure_fixture

import reflex as rx

configure_fixture()

config = rxe.Config(
    app_name="free_tier",
    frontend_port=3131,
    backend_port=8131,
    backend_host="127.0.0.1",
    telemetry_enabled=False,
    show_built_with_reflex=os.environ.get("QA_BADGE", "true") == "true",
    bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"),
    plugins=[rx.plugins.RadixThemesPlugin()],
)
