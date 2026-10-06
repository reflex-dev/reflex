"""Serve the same published local OIDC provider as the upstream auth tests."""

import os
import signal
import threading

from oidc_provider_mock import User, run_server_in_thread


def main() -> None:
    """Run the local provider until interrupted."""
    os.environ["AUTHLIB_INSECURE_TRANSPORT"] = "1"
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    users = [
        User(
            sub="alice",
            claims={
                "name": "Alice Admin",
                "email": "alice@example.com",
                "groups": ["admins", "staff"],
            },
        ),
        User(
            sub="bob",
            claims={
                "name": "Bob Member",
                "email": "bob@example.com",
                "groups": ["staff"],
            },
        ),
    ]
    with run_server_in_thread(port=9151, user_claims=users):
        print("Local OIDC provider listening at http://localhost:9151", flush=True)
        done.wait()


if __name__ == "__main__":
    main()
