"""Keep tooling probes within their fixture origin and credential directory."""

import os
import sys
from pathlib import Path


def install() -> None:
    """Install guards before importing any framework or CLI module."""
    root = Path(os.environ["TOOLING_FIXTURE_ROOT"]).resolve()
    port = int(os.environ.get("TOOLING_FIXTURE_PORT", "8580"))

    def audit(event: str, args: tuple) -> None:
        """Reject nonfixture connections and credential-file access.

        Args:
            event: Python audit event name.
            args: Event arguments.

        Raises:
            PermissionError: The operation leaves the fixture boundary.
        """
        if event == "socket.connect":
            address = args[1]
            if not isinstance(address, tuple) or address[:2] != ("127.0.0.1", port):
                raise PermissionError(
                    "Tooling fixture permits only its owned loopback origin"
                )
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0]))
            if path.name in (
                "hosting_v0.json",
                "hosting_v1.json",
                "hosting.json",
                "legacy.json",
            ) and not path.resolve().is_relative_to(root):
                raise PermissionError(
                    "Tooling fixture refuses nonfixture credential files"
                )

    sys.addaudithook(audit)
