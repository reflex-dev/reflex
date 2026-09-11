"""A stand-in Reflex Cloud control plane, so the CLI's rejected-token path can be
exercised without any real network (and without this sandbox's egress proxy).

  python fake_control_plane.py <port> <mode>

mode "reject" -> POST /api/v1/authenticate/me answers 403 with the shape a real
                 control plane uses for an expired/rotated token.
mode "accept" -> the same endpoint answers 200 with a user payload, and
                 /api/v1/deployments answers 200 with an empty app list.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
MODE = sys.argv[2]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write("REQ %s %s\n" % (self.command, self.path))
        sys.stderr.flush()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if self.path.startswith("/api/v1/authenticate/me"):
            if MODE == "reject":
                self._send(403, {"detail": "Invalid or expired token"})
            else:
                self._send(200, {"user_id": "u-1", "email": "someone@example.com"})
            return
        self._send(404, {"detail": "not found"})

    def do_GET(self):
        if MODE == "accept":
            self._send(200, [])
        else:
            self._send(403, {"detail": "Invalid or expired token"})


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
