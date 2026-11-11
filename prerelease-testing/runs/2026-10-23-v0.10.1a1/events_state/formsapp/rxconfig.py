import os

import reflex as rx

_api = os.environ.get("FORMS_API_URL")
config = rx.Config(
    app_name="formsapp",
    **({"api_url": _api} if _api else {}),
)
