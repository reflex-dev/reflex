"""A fake Reflex Cloud control plane for exercising reflex-hosting-cli offline.

Stdlib only. Serves the subset of ``/api/v1/`` that the hosting CLI calls, with
payload shapes derived from reflex_build_sdk.types, and records every request.

Run:  python -I fake_cp.py --port 8260 --state-dir <dir>
Point the CLI at it with REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:8260[/prefix]

Control endpoints (never prefixed):
  POST /__control/scenario   body: {"responses": {"<METHOD> <api_path regex>": [resp, ...]}}
                             each resp: {"status": int, "json": any | "text": str,
                                         "headers": {}, "delay": float, "drop": bool}
                             The list is consumed in order; the last entry repeats.
  POST /__control/reset      clears the scenario and the request log
  GET  /__control/log        the request log as JSON
Uploads reserved by POST deployments/reserve are PUT to /__upload/<id>/<archive>
and stored under <state-dir>/uploads/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

USER_ID = "00000000-0000-0000-0000-000000000001"
ORG_ID = "00000000-0000-0000-0000-000000000002"
PROJECT_ID = "00000000-0000-0000-0000-00000000aa01"
PROJECT2_ID = "00000000-0000-0000-0000-00000000aa02"
APP_ID = "00000000-0000-0000-0000-000000000a01"
APP_NAME = "cliapp"
DEPLOYMENT_ID = "00000000-0000-0000-0000-00000000d001"

ME = {
    "user_id": USER_ID,
    "org_id": ORG_ID,
    "email": "qa@example.invalid",
    "tier": "Pro",
    "is_service_account": False,
}

TIER_PRO = {"name": "Pro", "cpu_quota": 4, "ram_quota": 8, "deployment_quota": 10}
TIER_FREE = {"name": "Free", "cpu_quota": 1, "ram_quota": 1, "deployment_quota": 1}

PROJECTS = [
    {
        "id": PROJECT_ID,
        "name": "qa-project",
        "tier": TIER_PRO,
        "app_count": 1,
        "deployment_count": 3,
        "cpu_usage": 0.5,
        "memory_usage": 1.25,
    },
    {
        "id": PROJECT2_ID,
        "name": "second project",
        "tier": TIER_FREE,
        "app_count": 0,
        "deployment_count": 0,
        "cpu_usage": 0,
        "memory_usage": 0,
    },
]

PROJECT = {
    "id": PROJECT_ID,
    "name": "qa-project",
    "tier": TIER_PRO,
    "project_owner": USER_ID,
    "project_owner_email": "qa@example.invalid",
    "project_seats": 1,
    "org_cpu_usage": 0.5,
    "org_ram_usage": 1.25,
    "org_running_deployments": 1,
    "apps": [],
}

APP_SUMMARY = {
    "id": APP_ID,
    "name": APP_NAME,
    "description": "qa app",
    "project_id": PROJECT_ID,
    "provider": "fly",
    "disable_secrets": False,
}

APP = {
    **APP_SUMMARY,
    "org_id": ORG_ID,
    "full_deploy": False,
    "min_instances": None,
    "max_instances": None,
    "weekly_report_enabled": False,
    "source_thread_id": None,
    "unreleased_provider": None,
    "has_deployments": True,
    "backend_url": "https://cliapp-backend.example.invalid",
    "latest_deployment": None,
    "any_environment_live": True,
    "any_environment_stopped": False,
    "any_environment_paused": False,
    "any_environment_credit_paused": False,
}

GCP_STATUS = {
    "configured": False,
    "allowed": False,
    "project_id": None,
    "region": None,
    "connections": [],
}

REPORT_RUNNING = {
    "status": "Running",
    "code": None,
    "fault": None,
    "reason": "",
    "guidance": "",
    "build_log_excerpt": None,
}


def log_records() -> list[dict]:
    """Build a page of runtime log records, including awkward ones.

    Returns:
        The records, newest first.
    """
    base = 1_760_000_000
    records = [
        {
            "ns": (base + 10) * 10**9,
            "timestamp": "2026-10-23T12:00:10+00:00",
            "name": APP_NAME,
            "message": "plain info line",
            "details": None,
            "log_level": "info",
            "region": "sjc",
            "deployment_id": DEPLOYMENT_ID,
        },
        {
            "ns": (base + 9) * 10**9,
            "timestamp": "2026-10-23T12:00:09+00:00",
            "name": APP_NAME,
            "message": "warning with details",
            "details": "detail line 1\ndetail line 2",
            "log_level": "warning",
        },
        {
            # No optional fields at all: level must default.
            "ns": (base + 8) * 10**9,
            "timestamp": "2026-10-23T12:00:08+00:00",
            "name": APP_NAME,
            "message": "record without level/details/region",
        },
        {
            "ns": (base + 7) * 10**9,
            "timestamp": "2026-10-23T12:00:07+00:00",
            "name": APP_NAME,
            "message": {"event": "structured", "n": 3, "nested": {"ok": True}, "u": "ü"},
            "log_level": "error",
        },
        {
            "ns": (base + 6) * 10**9,
            "timestamp": "2026-10-23T12:00:06+00:00",
            "name": APP_NAME,
            "message": "unicode: héllo wörld 日本語 🚀 مرحبا",
            "log_level": "INFO",
        },
        {
            "ns": (base + 5) * 10**9,
            "timestamp": "2026-10-23T12:00:05+00:00",
            "name": APP_NAME,
            "message": "multi\nline\nmessage",
            "log_level": "debug",
        },
        {
            "ns": (base + 4) * 10**9,
            "timestamp": "2026-10-23T12:00:04+00:00",
            "name": APP_NAME,
            "message": "control chars: \x1b[31mred\x1b[0m \x07bell \r carriage \x00nul \ttab",
            "log_level": "info",
        },
        {
            "ns": (base + 3) * 10**9,
            "timestamp": "2026-10-23T12:00:03+00:00",
            "name": APP_NAME,
            "message": "rich markup [bold]not bold[/bold] :rocket: [link=http://x]x[/link]",
            "log_level": "info",
        },
        {
            "ns": (base + 2) * 10**9,
            "timestamp": "2026-10-23T12:00:02+00:00",
            "name": APP_NAME,
            "message": "HUGE " + ("x" * 20000) + " END",
            "log_level": "info",
        },
        {
            "ns": (base + 1) * 10**9,
            "timestamp": "2026-10-23T12:00:01+00:00",
            "name": APP_NAME,
            "message": "",
            "log_level": None,
        },
    ]
    return records


class State:
    """Mutable server state shared by handler threads."""

    def __init__(self, state_dir: Path) -> None:
        self.lock = threading.Lock()
        self.state_dir = state_dir
        self.upload_dir = state_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = state_dir / "requests.jsonl"
        self.requests: list[dict] = []
        self.scenario: dict[str, list[dict]] = {}
        self.counters: dict[str, int] = {}

    def reset(self, scenario: dict | None) -> None:
        with self.lock:
            self.requests = []
            self.counters = {}
            self.scenario = (scenario or {}).get("responses", {})
            self.log_path.write_text("")

    def record(self, entry: dict) -> None:
        with self.lock:
            self.requests.append(entry)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def scripted(self, key: str) -> dict | None:
        """Pick the scripted response for a request key, if any.

        Args:
            key: ``"<METHOD> <api_path>"``.

        Returns:
            The response spec, or None to use the default handler.
        """
        with self.lock:
            for pattern, responses in self.scenario.items():
                if re.fullmatch(pattern, key):
                    index = self.counters.get(pattern, 0)
                    self.counters[pattern] = index + 1
                    if not responses:
                        return None
                    return responses[min(index, len(responses) - 1)]
        return None


def masked(token: str | None) -> str | None:
    if not token:
        return token
    return "sha256:" + hashlib.sha256(token.encode()).hexdigest()[:16]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    state: State

    def log_message(self, format, *args):  # noqa: A002
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            return self.rfile.read(length)
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            chunks = []
            while True:
                size = int(self.rfile.readline().strip() or b"0", 16)
                if size == 0:
                    self.rfile.readline()
                    break
                chunks.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(chunks)
        return b""

    def _send(self, status: int, body: bytes = b"", headers: dict | None = None, content_type="application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_json(self, status: int, payload, headers: dict | None = None) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode(), headers)

    def _handle(self) -> None:
        parts = urlsplit(self.path)
        query = {k: v if len(v) > 1 else v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        body = self._read_body()
        entry = {
            "ts": time.time(),
            "method": self.command,
            "path": parts.path,
            "query": query,
            "request_id": self.headers.get("X-Request-ID"),
            "token": masked(self.headers.get("X-API-TOKEN")),
            "content_type": self.headers.get("Content-Type"),
            "user_agent": self.headers.get("User-Agent"),
            "body_len": len(body),
        }
        if entry["content_type"] and ("json" in entry["content_type"] or "form" in entry["content_type"]):
            entry["body"] = body[:4000].decode("utf-8", "replace")
        self.state.record(entry)

        if parts.path.startswith("/__control/"):
            return self._control(parts.path, body)
        if parts.path.startswith("/__upload/"):
            return self._upload(parts.path, body)

        if "/api/v1/" in parts.path:
            api_path = parts.path.split("/api/v1/", 1)[1]
        else:
            self._send_json(404, {"detail": f"no /api/v1/ in {parts.path}"})
            return
        key = f"{self.command} {api_path}"
        spec = self.state.scripted(key)
        if spec is not None:
            return self._scripted(spec)
        return self._default(self.command, api_path, query, body)

    def _control(self, path: str, body: bytes) -> None:
        if path == "/__control/scenario" or path == "/__control/reset":
            scenario = json.loads(body) if body else None
            self.state.reset(scenario)
            self._send_json(200, {"ok": True, "patterns": list(self.state.scenario)})
        elif path == "/__control/log":
            with self.state.lock:
                self._send_json(200, self.state.requests)
        else:
            self._send_json(404, {"detail": "unknown control"})

    def _upload(self, path: str, body: bytes) -> None:
        # /__upload/<deployment_id>/<archive>
        _, _, deployment_id, archive = path.split("/", 3)
        target = self.state.upload_dir / deployment_id
        target.mkdir(parents=True, exist_ok=True)
        (target / archive).write_bytes(body)
        self.state.record({"ts": time.time(), "upload_saved": str(target / archive), "size": len(body), "sha256": hashlib.sha256(body).hexdigest()})
        self._send(200, b"")

    def _scripted(self, spec: dict) -> None:
        if spec.get("delay"):
            time.sleep(float(spec["delay"]))
        if spec.get("drop"):
            # Close the connection without answering: the client cannot tell
            # whether the server processed the request.
            self.close_connection = True
            self.connection.close()
            return
        status = int(spec.get("status", 200))
        headers = spec.get("headers") or {}
        if "text" in spec:
            self._send(status, spec["text"].encode(), headers, content_type=spec.get("content_type", "text/plain"))
        else:
            self._send_json(status, spec.get("json"), headers)

    def _default(self, method: str, api_path: str, query: dict, body: bytes) -> None:
        if method == "POST" and api_path == "authenticate/me":
            return self._send_json(200, ME)
        if method == "GET" and api_path == "project":
            return self._send_json(200, PROJECTS)
        if method == "GET" and api_path == "project/search":
            name = query.get("project_name")
            return self._send_json(200, [{"id": p["id"], "name": p["name"]} for p in PROJECTS if p["name"] == name])
        if method == "GET" and api_path.startswith("project/"):
            pid = api_path.split("/", 1)[1]
            if pid in (PROJECT_ID, PROJECT2_ID):
                return self._send_json(200, {**PROJECT, "id": pid})
            return self._send_json(404, {"detail": "project not found"})
        if method == "GET" and api_path == "apps":
            return self._send_json(200, [APP_SUMMARY])
        if method == "GET" and api_path == "apps/search":
            name = query.get("app_name")
            return self._send_json(200, [APP_SUMMARY] if name == APP_NAME else [])
        if method == "POST" and api_path == "apps":
            return self._send_json(200, {"id": APP_ID})
        if method == "POST" and api_path == "apps/reserve":
            return self._send_json(200, {"hostname": "https://cliapp.example.invalid", "server": "https://cliapp-backend.example.invalid"})
        if method == "GET" and api_path == f"apps/{APP_ID}":
            return self._send_json(200, APP)
        if method == "GET" and api_path == f"apps/{APP_ID}/logsv2":
            return self._send_json(200, [log_records(), None])
        if method == "POST" and api_path == f"apps/{APP_ID}/instance_bounds":
            return self._send_json(200, {"status": "ok", "applied_now": False})
        if method == "POST" and api_path == f"apps/{APP_ID}/provider":
            return self._send_json(200, {"provider": "fly", "released": None})
        if method == "GET" and api_path == f"orgs/{ORG_ID}/provider-accounts/gcp/status":
            return self._send_json(200, GCP_STATUS)
        if method == "GET" and api_path == "deployments/validate_cli":
            return self._send_json(200, None)
        if method == "POST" and api_path == "deployments/reserve":
            data = json.loads(body)
            did = str(uuid.uuid4())
            host = f"http://{self.headers.get('Host')}"
            return self._send_json(200, {
                "deployment_id": did,
                "backend": {"url": f"{host}/__upload/{did}/backend.zip", "headers": {"x-goog-meta-size": str(data.get("backend_size"))}},
                "frontend": {"url": f"{host}/__upload/{did}/frontend.zip", "headers": {"x-goog-meta-size": str(data.get("frontend_size"))}},
            })
        if method == "POST" and api_path == "deployments":
            form = parse_qs(body.decode())
            did = form.get("stored_build_id", [DEPLOYMENT_ID])[0]
            return self._send_json(200, did)
        if method == "GET" and re.fullmatch(r"deployments/[^/]+/status", api_path):
            return self._send_json(200, "deployment completed successfully")
        if method == "GET" and re.fullmatch(r"deployments/[^/]+/failure", api_path):
            return self._send_json(200, REPORT_RUNNING)
        if method == "GET" and api_path == "deployments/regions":
            return self._send_json(200, [{"id": str(uuid.uuid4()), "name": "San Jose", "code": "sjc"}])
        if method == "GET" and api_path == "deployments/vm_types":
            return self._send_json(200, [{"id": "c1m1", "name": "c1m1", "cpu": 1, "ram": 1, "cpu_kind": "SHARED"}])
        if method == "GET" and api_path == "cli/token":
            return self._send_json(404, {"detail": "not approved yet"})
        return self._send_json(404, {"detail": f"fake_cp: unhandled {method} {api_path}"})

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_DELETE = _handle
    do_PATCH = _handle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    Handler.state = State(Path(args.state_dir))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    print(f"fake_cp listening on 127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
