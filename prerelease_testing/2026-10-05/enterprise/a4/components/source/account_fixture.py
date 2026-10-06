"""Run a loopback-only fictional account endpoint for component production QA."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class AccountAPI(BaseHTTPRequestHandler):
    """Answer the published SDK's identity validation endpoint."""

    def do_POST(self) -> None:
        """Validate the fictional credential and record a minimal wire trace."""
        path = urlsplit(self.path).path
        authorized = self.headers.get("X-API-TOKEN") == os.environ["QA_FIXTURE_TOKEN"]
        status = (
            200
            if path.removeprefix("/api/v1") == "/authenticate/me" and authorized
            else 401
        )
        response = (
            {
                "user_id": "11111111-1111-4111-8111-111111111111",
                "org_id": "22222222-2222-4222-8222-222222222222",
                "email": "components-a3@example.test",
                "tier": "Pro",
            }
            if status == 200
            else {"detail": "Fixture rejected unknown request"}
        )
        entry = {
            "method": self.command,
            "path": path,
            "only_fixture_credential": authorized,
            "status": status,
            "response_tier": "Pro",
        }
        with Path(os.environ["QA_ACCOUNT_AUDIT"]).open("a") as output:
            output.write(json.dumps(entry) + "\n")
        payload = json.dumps(response).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        """Suppress routine HTTP console output.

        Args:
            format: HTTP log format.
            *args: HTTP log arguments.
        """


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), AccountAPI)
    Path(os.environ["QA_ACCOUNT_PORT_FILE"]).write_text(str(server.server_port))
    print(
        f"Fictional account fixture on loopback port {server.server_port}", flush=True
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
