"""Minimal OTLP/HTTP receiver: POST /v1/traces and /v1/metrics.

Usage: otlp_receiver.py <port> <outdir> [--no-cors]

Accepts protobuf (application/x-protobuf, optionally gzip) and JSON bodies.
Appends one JSON line per export to <outdir>/traces.jsonl / metrics.jsonl and
logs every request to <outdir>/access.log.
"""

from __future__ import annotations

import gzip
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(sys.argv[1])
OUT = Path(sys.argv[2])
CORS = "--no-cors" not in sys.argv
OUT.mkdir(parents=True, exist_ok=True)
ACCESS = OUT / "access.log"


def log(msg: str) -> None:
    with ACCESS.open("a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def decode(body: bytes, ctype: str, kind: str):
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    if "json" in ctype:
        return json.loads(body.decode())
    from google.protobuf.json_format import MessageToDict

    if kind == "traces":
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
            ExportTraceServiceRequest as Req,
        )
    else:
        from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
            ExportMetricsServiceRequest as Req,
        )
    m = Req()
    m.ParseFromString(body)
    return MessageToDict(m, preserving_proto_field_name=True)


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        if CORS:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Max-Age", "600")

    def do_OPTIONS(self):  # noqa: N802
        log(f"OPTIONS {self.path} origin={self.headers.get('Origin')} cors={CORS}")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self._cors()
        body = b'{"ok":true}'
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        ctype = self.headers.get("Content-Type", "")
        kind = "traces" if self.path.endswith("/v1/traces") else "metrics"
        log(
            f"POST {self.path} ctype={ctype} len={n} origin={self.headers.get('Origin')} "
            f"traceparent={self.headers.get('traceparent')} cors={CORS}"
        )
        try:
            data = decode(body, ctype, kind)
        except Exception as e:  # noqa: BLE001
            log(f"  DECODE FAILED: {e!r}")
            data = {"_raw_len": n, "_error": repr(e)}
        with (OUT / f"{kind}.jsonl").open("a") as f:
            f.write(json.dumps(data) + "\n")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


ThreadingHTTPServer.allow_reuse_address = True
srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
log(f"receiver listening on 127.0.0.1:{PORT} cors={CORS} out={OUT}")
srv.serve_forever()
