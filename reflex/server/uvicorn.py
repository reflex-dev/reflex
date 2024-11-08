"""The UvicornBackendServer."""

from __future__ import annotations

import sys

from reflex.constants.base import Env, LogLevel
from reflex.server.base import CustomBackendServer
from reflex.utils import console


# TODO
class UvicornBackendServer(CustomBackendServer):
    """Uvicorn backendServer."""

    def check_import(self, extra: bool = False):
        """Check package importation."""
        from importlib.util import find_spec

        errors: list[str] = []

        if find_spec("uvicorn") is None:
            errors.append(
                'The `uvicorn` package is required to run `UvicornBackendServer`. Run `pip install "uvicorn>=0.20.0"`.'
            )

        if errors:
            console.error("\n".join(errors))
            sys.exit()

    def setup(self, host: str, port: int, loglevel: LogLevel, env: Env):
        """Setup."""
        pass

    def run_prod(self):
        """Run in production mode."""
        pass

    def run_dev(self):
        """Run in development mode."""
        pass
