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
    # As of 9/29, it takes ~90 seconds for the backend to come up.
    BACKEND_POLL_TIMEOUT = 120
    # The time to wait for the frontend to come up after user initiates deployment. In seconds.
    # As of 9/29, the backend is deployed before frontend.
    # So likely when the backend is up, the frontend is pretty much up, since they're just static files.
    FRONTEND_POLL_TIMEOUT = 60
