"""Loopback-only fictional Reflex account API (adapted from the 2026-10-05 campaign).

Binds 127.0.0.1:8319 (inside this cluster's reserved range). Answers the hosting
SDK's POST /api/v1/authenticate/me for the fake token in QA_FIXTURE_TOKEN with the
tier in QA_TIER (default Pro); every request is appended to QA_ACCOUNT_AUDIT.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class AccountAPI(BaseHTTPRequestHandler):
    def _handle(self) -> None:
        path = urlsplit(self.path).path
        authorized = self.headers.get("X-API-TOKEN") == os.environ["QA_FIXTURE_TOKEN"]
        ok = path.removeprefix("/api/v1") == "/authenticate/me" and authorized
        tier = os.environ.get("QA_TIER", "Pro")
        body = (
            {"user_id": "11111111-1111-4111-8111-111111111111", "org_id": "22222222-2222-4222-8222-222222222222",
             "email": "ent-demos-qa@example.test", "tier": tier}
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
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8319), AccountAPI)
    print("fictional account fixture on 127.0.0.1:8319", flush=True)
    server.serve_forever()
