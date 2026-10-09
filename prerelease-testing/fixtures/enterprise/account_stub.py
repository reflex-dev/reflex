"""Loopback-only fictional Reflex Cloud account API for prod runs on the PyPI reflex-enterprise wheel.

The PyPI wheel (not the offline build) refuses `reflex run --env prod` / `reflex export` for an anonymous (logged-out)
user (`reflex_enterprise.utils.check_paid_tier_for_command`). lib.sh `acct_stub` starts this on 127.0.0.1:8639 and points
the server at it (REFLEX_CLOUD_BACKEND_URL + a fake REFLEX_ACCESS_TOKEN), so no real account or credential is involved.
Answers POST/GET /api/v1/authenticate/me for QA_FIXTURE_TOKEN with tier QA_TIER (default Pro); logs every request to
QA_ACCOUNT_AUDIT. Adapted from the 10-05/10-06 campaigns' account fixture.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class AccountAPI(BaseHTTPRequestHandler):
    """Answer the hosting SDK's authenticate/me call."""

    def _handle(self) -> None:
        """Reply 200 with the fixture tier for the fixture token, 401 otherwise."""
        path = urlsplit(self.path).path
        authorized = self.headers.get("X-API-TOKEN") == os.environ["QA_FIXTURE_TOKEN"]
        ok = path.removeprefix("/api/v1") == "/authenticate/me" and authorized
        tier = os.environ.get("QA_TIER", "Pro")
        body = (
            {"user_id": "11111111-1111-4111-8111-111111111111", "org_id": "22222222-2222-4222-8222-222222222222",
             "email": "ent-fixtures-qa@example.test", "tier": tier}
            if ok else {"detail": "fixture rejected request"}
        )
        with Path(os.environ["QA_ACCOUNT_AUDIT"]).open("a") as f:
            f.write(json.dumps({"method": self.command, "path": path, "authorized": authorized, "status": 200 if ok else 401, "tier": tier}) + "\n")
        payload = json.dumps(body).encode()
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_POST = _handle
    do_GET = _handle

    def log_message(self, format, *args) -> None:
        """Silence the default access log."""


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("QA_ACCOUNT_PORT", "8639"))), AccountAPI)
    print(f"fictional account fixture on {server.server_address}", flush=True)
    server.serve_forever()
