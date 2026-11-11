import os

import reflex as rx

_kw = {}
if os.environ.get("CS_AUTO_MEMO") == "0":
    _kw["auto_memoize"] = False
if os.environ.get("CS_COMPILER") == "1":
    _kw["react_compiler"] = True

config = rx.Config(app_name="csedge", telemetry_enabled=False, plugins=[rx.plugins.RadixThemesPlugin()], **_kw)
