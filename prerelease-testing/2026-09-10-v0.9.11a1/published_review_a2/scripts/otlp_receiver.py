"""A minimal OTLP/HTTP receiver that records what it is sent.

Usage: python otlp_receiver.py <port> <out.json>
Accepts POST /v1/traces, /v1/metrics, /v1/logs, answers 200 with an empty
protobuf body, and appends one record per request to <out.json>.
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1])
OUT = sys.argv[2]
RECORDS = []
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    """Record every OTLP POST."""

    def do_POST(self):  # noqa: N802
        """Accept and record a payload."""
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        with LOCK:
            RECORDS.append({
                "t": time.time(),
                "path": self.path,
                "content_type": self.headers.get("Content-Type"),
                "content_encoding": self.headers.get("Content-Encoding"),
                "bytes": len(body),
                "user_agent": self.headers.get("User-Agent"),
            })
            with open(OUT, "w") as f:
                json.dump(RECORDS, f, indent=1)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        """Expose the record list for assertions."""
        with LOCK:
            payload = json.dumps(RECORDS).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        """Silence the default stderr logging."""


HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
