"""Route account credentials and Python networking to the local fixture."""

import json
import os
import sys
from pathlib import Path

from reflex_cli import constants
from reflex_enterprise.constants import IS_OFFLINE
from reflex_enterprise.environment import environment

from reflex.constants import APP_HARNESS_FLAG

_audit_installed = False


def configure_fixture() -> None:
    """Redirect credential paths and install the loopback-only network audit.

    Raises:
        ValueError: If a credential path is outside the disposable directory.
    """
    global _audit_installed
    credentials = Path(os.environ["TEST_HOSTING_CONFIG"])
    if not credentials.is_relative_to(Path("/private/tmp")):
        raise ValueError("Fixture credentials must live under /private/tmp")
    constants.Hosting.HOSTING_JSON = credentials
    constants.Hosting.HOSTING_JSON_V0 = credentials.with_name("legacy.json")
    context = {
        "pid": os.getpid(),
        "ci_env_present": "CI" in os.environ,
        "ci_parser_value": environment.CI.get(),
        "app_harness_env_present": APP_HARNESS_FLAG in os.environ,
        "offline_distribution": IS_OFFLINE,
        "credential_path": str(credentials),
    }
    with Path(os.environ["TEST_CONTEXT_AUDIT"]).open("a") as output:
        output.write(json.dumps(context) + "\n")
    if not _audit_installed:
        sys.addaudithook(audit_network)
        _audit_installed = True


def audit_network(event: str, args: tuple) -> None:
    """Record outbound Python sockets and reject non-loopback destinations.

    Args:
        event: Python audit event.
        args: Event arguments.

    Raises:
        RuntimeError: If an outbound Python socket targets a remote address.
    """
    if event != "socket.connect":
        return
    address = args[1]
    if not isinstance(address, tuple):
        return
    host = address[0]
    allowed = host in {"127.0.0.1", "::1", "localhost"}
    entry = {"pid": os.getpid(), "host": host, "port": address[1], "allowed": allowed}
    descriptor = os.open(
        os.environ["TEST_NETWORK_AUDIT"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
    )
    try:
        os.write(descriptor, (json.dumps(entry) + "\n").encode())
    finally:
        os.close(descriptor)
    if not allowed:
        raise RuntimeError(f"Fixture rejected non-loopback Python connection: {host}")
