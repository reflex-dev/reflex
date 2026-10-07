"""Configure a short session lifetime for the independent expiry verifier."""

import os

import reflex as rx

config = rx.Config(
    app_name="export_desk",
    telemetry_enabled=False,
    state_manager_mode=os.environ["VERIFY_MANAGER"],
    redis_token_expiration=int(os.environ["VERIFY_TTL"]),
)
