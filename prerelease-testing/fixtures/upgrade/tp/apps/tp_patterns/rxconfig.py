import os as _os

import reflex as rx

# venv guard (a3_events_tp): bin/start_app.sh exports TP_EXPECT_VENV, the AppHarness tests export TP_VENV
_EXPECT_VENV = _os.environ.get("TP_EXPECT_VENV") or _os.environ.get("TP_VENV", "")
assert _EXPECT_VENV and f"/envs/{_EXPECT_VENV}/" in rx.__file__, (rx.__file__, _EXPECT_VENV)

config = rx.Config(
    app_name="tp_patterns",
    # setvar() needs the generated set_<var> setters.
    state_auto_setters=True,
    plugins=[rx.plugins.SitemapPlugin(), rx.plugins.RadixThemesPlugin()],
)
