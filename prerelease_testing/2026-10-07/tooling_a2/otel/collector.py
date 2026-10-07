"""Receive actual OTLP JSON/protobuf exports on a task-owned localhost port."""

import argparse
import gzip
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)


def main():
    """Serve a CORS-enabled local collector and append complete decoded requests."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8588)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        """Implement the minimal OTLP/HTTP trace receiver contract."""

        def log_message(self, fmt, *values):
            """Write ordinary request diagnostics.

            Args:
                fmt: Message format.
                *values: Format arguments.
            """
            print(fmt % values, flush=True)

        def respond(self, code, body=b"{}", content_type="application/json"):
            """Return CORS headers and an OTLP-compatible response.

            Args:
                code: HTTP response code.
                body: Encoded response body.
                content_type: Response media type.
            """
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers", "content-type,x-qa-collector"
            )
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            """Expose a readiness endpoint."""
            self.respond(200)

        def do_OPTIONS(self):
            """Allow cross-origin browser exports."""
            self.respond(204, b"")

        def do_POST(self):
            """Decode and retain one real OTLP export request."""
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            content_type = self.headers.get("Content-Type", "")
            try:
                if "json" in content_type:
                    decoded = json.loads(raw)
                else:
                    message = ExportTraceServiceRequest()
                    message.ParseFromString(raw)
                    decoded = MessageToDict(message)
                row = {
                    "time": time.time(),
                    "path": self.path,
                    "content_type": content_type,
                    "origin": self.headers.get("Origin"),
                    "public_header": self.headers.get("x-qa-collector"),
                    "body_bytes": len(raw),
                    "decoded": decoded,
                }
                with lock, args.out.open("a") as output:
                    output.write(json.dumps(row) + "\n")
                self.respond(
                    200, b"{}" if "json" in content_type else b"", content_type
                )
            except Exception as error:
                print(f"COLLECTOR_DECODE_ERROR {error!r}", flush=True)
                self.respond(400)

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
