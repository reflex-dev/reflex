"""Keep component-lane cloud credentials and networking confined to fixtures."""

import json
import os
import sys
from pathlib import Path

from reflex_cli import constants


def configure_fixture() -> None:
    """Redirect cloud credentials and verify published framework provenance."""
    credentials = Path(os.environ["TEST_HOSTING_CONFIG"]).resolve()
    assert credentials.is_relative_to(Path("/private/tmp"))
    contents = json.loads(credentials.read_text())
    expected = os.environ.get("QA_FIXTURE_TOKEN")
    assert contents == ({"access_token": expected} if expected else {})
    constants.Hosting.HOSTING_JSON = credentials
    constants.Hosting.HOSTING_JSON_V0 = credentials.with_name("legacy-hosting.json")
    assert "REFLEX_ACCESS_TOKEN" not in os.environ
    import reflex
    import reflex_enterprise

    if context_path := os.environ.get("QA_CONTEXT_AUDIT"):
        from reflex.constants import APP_HARNESS_FLAG
        from reflex_enterprise.constants import IS_OFFLINE
        from reflex_enterprise.environment import environment

        context = {
            "pid": os.getpid(),
            "ci_env_present": "CI" in os.environ,
            "ci_parser_value": environment.CI.get(),
            "app_harness_env_present": APP_HARNESS_FLAG in os.environ,
            "offline_distribution": IS_OFFLINE,
            "credential_path": str(credentials),
            "fictional_credential": bool(expected),
        }
        with Path(context_path).open("a") as output:
            output.write(json.dumps(context) + "\n")
    global _audit_installed
    if expected and not _audit_installed:
        sys.addaudithook(audit_network)
        _audit_installed = True
    for module in (reflex, reflex_enterprise):
        assert Path(module.__file__).is_relative_to(Path(sys.prefix))
        assert "site-packages" in module.__file__


_audit_installed = False


def audit_network(event: str, args: tuple) -> None:
    """Reject remote Python connections in the production account fixture.

    Args:
        event: Audit event name.
        args: Audit event arguments.

    Raises:
        RuntimeError: If a Python socket connects outside loopback.
    """
    if event != "socket.connect" or not isinstance(args[1], tuple):
        return
    host, port = args[1][:2]
    allowed = host in {"127.0.0.1", "::1", "localhost"}
    entry = {"pid": os.getpid(), "host": host, "port": port, "allowed": allowed}
    descriptor = os.open(
        os.environ["QA_NETWORK_AUDIT"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
    )
    try:
        os.write(descriptor, (json.dumps(entry) + "\n").encode())
    finally:
        os.close(descriptor)
    if not allowed:
        raise RuntimeError(f"Fixture rejected non-loopback Python connection: {host}")
