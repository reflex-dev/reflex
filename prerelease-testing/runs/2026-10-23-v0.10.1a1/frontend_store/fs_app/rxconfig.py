import os

import reflex as rx

# FS_TW_IMPORTANT=1 adds the tailwind `important` option (#7573); default off so
# the baseline comparison with 0.10.0 stays byte-comparable.
_plugins = []
if os.environ.get("FS_TW_IMPORTANT") == "1":
    _plugins.append(rx.plugins.TailwindV4Plugin(config={"important": True}))

config = rx.Config(
    app_name="fs_app",
    plugins=_plugins,
    # react_compiler is NOT set here: the env var REFLEX_REACT_COMPILER drives it
    # so the same app serves the on/off comparison (#7234).
)
