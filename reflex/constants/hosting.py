"""Constants related to hosting."""
import os

from reflex.constants.base import Reflex


class Hosting:
    """Constants related to hosting."""

    # The hosting config json file
    HOSTING_JSON = os.path.join(Reflex.DIR, "config.json")
    # The time to wait for the user to complete web authentication. In seconds.
    WEB_AUTH_TIMEOUT = 300
    # The time to wait for the backend to come up after user initiates deployment. In seconds.
    BACKEND_POLL_TIMEOUT = 120
    # The time to wait for the frontend to come up after user initiates deployment. In seconds.
    FRONTEND_POLL_TIMEOUT = 120
