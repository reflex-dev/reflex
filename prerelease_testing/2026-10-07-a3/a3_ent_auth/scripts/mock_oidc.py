"""Local OIDC provider (published oidc-provider-mock) for the ent_auth_mcp_redis cluster.

Env:
  MOCK_OIDC_PORT        (default 8358)
  MOCK_OIDC_MAX_AGE     access/id/refresh token lifetime in seconds (default 3600)
  MOCK_OIDC_NO_REFRESH  set to 1 to not issue refresh tokens
"""

import os
import signal
import sys
import threading
from datetime import timedelta

import oidc_provider_mock

assert "/scratchpad/envs/alpha2-ent/" in oidc_provider_mock.__file__, oidc_provider_mock.__file__

from oidc_provider_mock import User, run_server_in_thread


def main() -> None:
    os.environ["AUTHLIB_INSECURE_TRANSPORT"] = "1"
    port = int(os.environ.get("MOCK_OIDC_PORT", "8358"))
    max_age = int(os.environ.get("MOCK_OIDC_MAX_AGE", "3600"))
    issue_refresh = not os.environ.get("MOCK_OIDC_NO_REFRESH")
    done = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: done.set())
    signal.signal(signal.SIGINT, lambda *_: done.set())
    users = [
        User(sub="alice", claims={"name": "Alice Admin", "email": "alice@example.com", "groups": ["admins", "staff"]}),
        User(sub="bob", claims={"name": "Bob Member", "email": "bob@example.com", "groups": ["staff"]}),
    ]
    with run_server_in_thread(
        port=port,
        user_claims=users,
        access_token_max_age=timedelta(seconds=max_age),
        issue_refresh_token=issue_refresh,
    ):
        print(f"Local OIDC provider http://localhost:{port} max_age={max_age} refresh={issue_refresh} pid={os.getpid()}", flush=True)
        done.wait()
    sys.exit(0)


if __name__ == "__main__":
    main()
