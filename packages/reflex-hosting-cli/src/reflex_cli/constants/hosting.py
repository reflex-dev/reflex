"""Constants related to hosting."""

import os
from pathlib import Path
from types import SimpleNamespace

from packaging import version

from reflex_cli.constants.base import Reflex


class ReflexHostingCli(SimpleNamespace):
    """Constants related to reflex-hosting-cli."""

    MODULE_NAME = "reflex-hosting-cli"

    MINIMUM_REFLEX_VERSION = version.parse("0.6.6.post1")

    RECOMMENDED_REFLEX_VERSION = version.parse("0.7.6")


class Hosting(SimpleNamespace):
    """Constants related to hosting."""

    # The hosting config json file
    HOSTING_JSON = Path(Reflex.DIR) / "hosting_v1.json"
    HOSTING_JSON_V0 = Path(Reflex.DIR) / "hosting_v0.json"
    # The hosting service backend URL
    HOSTING_SERVICE = os.environ.get(
        "REFLEX_CLOUD_BACKEND_URL",
        os.environ.get("CP_BACKEND_URL", "https://build.reflex.dev"),
    )
    # The hosting service webpage URL
    HOSTING_SERVICE_UI = os.environ.get(
        "REFLEX_CLOUD_URL", os.environ.get("CP_WEB_URL", "https://build.reflex.dev")
    )
    # The time to wait for HTTP requests to the backend
    TIMEOUT = 10
    # The number of times to retry authentication
    AUTH_RETRY_LIMIT = 5
    # How long to wait between retry attempts
    AUTH_RETRY_SLEEP_DURATION = 5

    # Aliases for compatibility with previous versions of Reflex
    CP_BACKEND_URL = HOSTING_SERVICE
    CP_WEB_URL = HOSTING_SERVICE_UI


class RequirementsTxt(SimpleNamespace):
    """Requirements.txt constants."""

    # The requirements.txt file.
    FILE = "requirements.txt"

    # The pyproject.toml file.
    PYPROJECT = "pyproject.toml"
