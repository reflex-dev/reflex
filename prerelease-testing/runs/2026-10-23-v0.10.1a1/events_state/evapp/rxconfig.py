import os

import reflex as rx

_api = os.environ.get("EV_API_URL")
config = rx.Config(
    app_name="evapp",
    **({"api_url": _api} if _api else {}),
)
