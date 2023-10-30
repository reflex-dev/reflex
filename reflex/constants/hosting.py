"""Constants related to hosting."""
import os

from reflex.constants.base import Reflex


class Hosting:
    """Constants related to hosting."""

    # The hosting config json file
    HOSTING_JSON = os.path.join(Reflex.DIR, "hosting_v0.json")
    # The hosting service backend URL
    CP_BACKEND_URL = "https://rxcp-prod-control-plane.fly.dev"
    # The hosting service webpage URL
    CP_WEB_URL = "https://control-plane.reflex.run"

    # The number of times to try and wait for the user to complete web authentication.
    WEB_AUTH_RETRIES = 60
    # The time to sleep between requests to check if for authentication completion. In seconds.
    WEB_AUTH_SLEEP_DURATION = 5
    # The time to wait for the backend to come up after user initiates deployment. In seconds.
    BACKEND_POLL_RETRIES = 45
    # The time to wait for the frontend to come up after user initiates deployment. In seconds.
    FRONTEND_POLL_RETRIES = 30
