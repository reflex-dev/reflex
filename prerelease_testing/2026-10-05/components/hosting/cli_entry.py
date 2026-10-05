"""Run the public installed CLI with fixture credentials and local sockets."""

import os
import sys
from pathlib import Path

import reflex
from reflex_cli import constants


def local_connections(event: str, args: tuple) -> None:
    """Refuse every socket connection outside the local fixture service.

    Args:
        event: Python audit event.
        args: Audit event arguments.

    Raises:
        OSError: When a connection targets a nonlocal address.
    """
    if event == "socket.connect" and args[1][0] not in ("127.0.0.1", "::1"):
        message = "Fixture permits only loopback HTTP connections"
        raise OSError(message)


assert Path(reflex.__file__).is_relative_to(Path(sys.prefix)), reflex.__file__
constants.Hosting.HOSTING_JSON = Path(os.environ["TEST_HOSTING_CONFIG"])
constants.Hosting.HOSTING_JSON_V0 = constants.Hosting.HOSTING_JSON.with_name(
    "legacy.json"
)
sys.addaudithook(local_connections)

from reflex.reflex import cli  # noqa: E402

cli()
