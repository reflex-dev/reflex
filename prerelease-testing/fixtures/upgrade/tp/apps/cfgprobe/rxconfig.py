import os as _os

import reflex as rx

# venv guard (a3_events_tp): bin/start_app.sh exports TP_EXPECT_VENV, the AppHarness tests export TP_VENV
_EXPECT_VENV = _os.environ.get("TP_EXPECT_VENV") or _os.environ.get("TP_VENV", "")
assert _EXPECT_VENV and f"/envs/{_EXPECT_VENV}/" in rx.__file__, (rx.__file__, _EXPECT_VENV)

# Values that differ from the defaults, read back inside a backend event handler.
config = rx.Config(
    app_name="cfgprobe",
    state_auto_setters=True,
    redis_lock_expiration=12345,
    default_color_mode="dark",
    telemetry_enabled=False,
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
