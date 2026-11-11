import os

import reflex as rx

_kw = {}
if os.environ.get("CV_AUTO_MEMO") == "0":
    _kw["auto_memoize"] = False
config = rx.Config(app_name="cvb", telemetry_enabled=False, plugins=[rx.plugins.RadixThemesPlugin()], **_kw)
