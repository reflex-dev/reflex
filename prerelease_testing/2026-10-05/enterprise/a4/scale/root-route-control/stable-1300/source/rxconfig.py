from pathlib import Path
import reflex as rx
config = rx.Config(app_name="lifecycle_app", frontend_port=3146, backend_port=3146, api_url="http://localhost:3146", telemetry_enabled=False, state_manager_mode="disk", bun_path=Path("/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"), plugins=[rx.plugins.RadixThemesPlugin()])
