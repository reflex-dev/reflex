"""Verify the owned auth test ports and campaign-specific shell isolation."""

import json
import socket
import sys
from pathlib import Path


def main() -> None:
    """Assert owned ports are released and save narrowly scoped cleanup facts."""
    result = {"ports": {}, "bun_installer_used": False}
    for port in (3152, 8152, 9151):
        with socket.socket() as client:
            client.settimeout(1)
            listening = client.connect_ex(("127.0.0.1", port)) == 0
        result["ports"][str(port)] = {"listening": listening}
        assert not listening, port
    shell = Path.home() / ".zshrc"
    text = shell.read_text() if shell.exists() else ""
    result["owned_bun_shell_paths_present"] = {
        path: path in text
        for path in (
            "/private/tmp/reflex-alpha-core-state/runtime/bun",
            "/private/tmp/reflex-enterprise-a3-20261005-runtime-stable/bun",
            "/private/tmp/reflex-enterprise-a3-20261005-runtime-narrow-alpha/bun",
            "/private/tmp/reflex-enterprise-a3-20261005-runtime-narrow-stable/bun",
            "/private/tmp/reflex-enterprise-a3-20261005-runtime-stable-min/bun",
        )
    }
    assert not any(result["owned_bun_shell_paths_present"].values())
    result["status"] = "passed"
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
