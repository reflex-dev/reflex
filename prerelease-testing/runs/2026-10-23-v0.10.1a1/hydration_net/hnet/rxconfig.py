import os

import reflex as rx

# HNET_HOPS -> trusted_proxy_hops (#7614). REFLEX_TRUSTED_PROXY_HOPS also works via the env var path.
_hops = os.environ.get("HNET_HOPS")
config = rx.Config(
    app_name="hnet",
    telemetry_enabled=False,
    **({"trusted_proxy_hops": int(_hops)} if _hops is not None else {}),
)
