"""Exercise new published hosting contracts through real local HTTP and CLI."""

import argparse
import copy
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import reflex
import reflex_cli

UV = "/Users/masenf/.local/bin/uv"
APP_ID = "11111111-1111-4111-8111-111111111111"
PROJECT_ID = "22222222-2222-4222-8222-222222222222"
ROLE_ID = "33333333-3333-4333-8333-333333333333"
DEPLOYMENT_ID = "44444444-4444-4444-8444-444444444444"
SECRET_VALUES = (
    "sentinel-only-for-fixture",
    "fixture=a=b",
    "file-only-value",
    "ignored-cli-value",
)
TIMESTAMP = "2026-10-05T12:34:56+00:00"


def deployment() -> dict:
    """Return a complete real SDK history wire record.

    Returns:
        A deployment record with nullable metadata and a VM type.
    """
    return {
        "id": DEPLOYMENT_ID,
        "url": "https://qa.example.test",
        "backend_url": "https://api.example.test",
        "status": "Running",
        "pause_reason": None,
        "failure_code": None,
        "failure_reason": None,
        "description": "Promoted release",
        "reflex_version": "0.10.0a1",
        "python_version": "3.13.7",
        "timestamp": TIMESTAMP,
        "last_updated": None,
        "deployment_user": None,
        "last_updated_by": None,
        "vm_type": {"id": "c2m4", "name": "Two cores / 4 GB", "cpu": 2.0, "ram": 4.0},
        "environment_id": None,
        "environment_name": "production",
        "promoted_from_deployment_id": None,
        "can_rollback": True,
    }


def app_document() -> dict:
    """Return a complete app with its production deployment wire aliases.

    Returns:
        An app inspect response.
    """
    return {
        "id": APP_ID,
        "name": "qa-app",
        "description": "Local fixture",
        "project_id": PROJECT_ID,
        "org_id": APP_ID,
        "provider": "gcp",
        "full_deploy": True,
        "min_instances": 1,
        "max_instances": 4,
        "disable_secrets": False,
        "weekly_report_enabled": False,
        "source_thread_id": None,
        "unreleased_provider": None,
        "has_deployments": True,
        "backend_url": "https://api.example.test",
        "any_environment_live": True,
        "any_environment_stopped": False,
        "any_environment_paused": False,
        "any_environment_credit_paused": False,
        "latest_deployment": {
            "id": DEPLOYMENT_ID,
            "url": "https://qa.example.test",
            "status": "Running",
            "pause_reason": None,
            "reflex_version": "0.10.0a1",
            "python_version": "3.13.7",
            "timestamp": TIMESTAMP,
            "regions": ["sjc", "lhr"],
            "vm_type_name": "Two cores / 4 GB",
            "vm_type_cpu": 2.0,
            "vm_type_ram": 4.0,
            "strategy": "rolling",
            "persist": True,
            "screenshot_uri": None,
            "last_updated": TIMESTAMP,
            "last_updated_by": {"id": APP_ID, "username": "qa@example.test"},
        },
    }


class MockAPI(BaseHTTPRequestHandler):
    """Serve complete wire fixtures and retain endpoint request evidence."""

    def log_message(self, *args) -> None:
        """Suppress normal server log noise.

        Args:
            *args: HTTP server log arguments.
        """

    def do_GET(self) -> None:
        """Respond to a real SDK GET request."""
        self.respond()

    def do_POST(self) -> None:
        """Respond to a real SDK POST request."""
        self.respond()

    def respond(self) -> None:
        """Record the request and return the selected realistic wire response."""
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length)) if length else None
        self.server.requests.append({
            "method": self.command,
            "path": self.path,
            "body": body,
        })
        path = urlsplit(self.path).path.removeprefix("/api/v1")
        scenario = self.server.scenario
        status = 200
        if path == "/authenticate/me":
            response = {
                "user_id": APP_ID,
                "org_id": APP_ID,
                "email": "qa@example.test",
                "tier": "Enterprise",
            }
        elif scenario == "refused":
            status, response = 403, {"detail": "Fixture request is forbidden"}
        elif path == f"/apps/{APP_ID}/history":
            record = deployment()
            if scenario == "nullable":
                record.update(
                    vm_type=None, url=None, description=None, can_rollback=False
                )
            response = [] if scenario == "empty" else [record]
        elif path == f"/apps/{APP_ID}":
            response = app_document()
            if scenario == "nullable":
                response.update(
                    latest_deployment=None,
                    has_deployments=False,
                    backend_url=None,
                    any_environment_live=False,
                )
        elif path == "/user/token/create":
            response = {
                "name": "server-renamed-token",
                "token": "created-fixture-token",
                "expiration": None
                if scenario == "nullable"
                else "2026-10-12T12:34:56+00:00",
            }
        elif path == f"/apps/{APP_ID}/secrets":
            response = (
                []
                if self.command == "GET"
                else {"message": "Server response must not leak fixture secrets"}
            )
        elif path == f"/project/{PROJECT_ID}/role/{ROLE_ID}":
            response = (
                None
                if scenario == "nullable"
                else [
                    {"name": "can_deploy", "id": 1},
                    {"name": "can_view_secret_keys", "id": 2},
                ]
            )
        elif path == f"/project/{PROJECT_ID}" or path == "/project/not-a-project-uuid":
            status, response = 404, {"detail": "Fixture project does not exist"}
        else:
            status, response = 500, {"detail": "Unexpected fixture endpoint"}
        content = json.dumps(response).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def invoke(args: list[str], cwd: Path, settings: dict[str, str]) -> dict:
    """Run the unmodified installed public CLI entry point.

    Args:
        args: Public CLI arguments.
        cwd: Neutral fixture or initialized test app.
        settings: Fixture environment overrides.

    Returns:
        Exit code, output streams and arguments.
    """
    env = dict(os.environ, **settings)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            UV,
            "run",
            "--no-project",
            "--python",
            sys.executable,
            "python",
            str(Path(__file__).with_name("cli_entry.py")),
            *args,
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "args": args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def verify(name: str, result: dict) -> None:
    """Verify CLI outputs against the new contracts and request boundaries.

    Args:
        name: Scenario name.
        result: CLI output and captured requests.
    """
    expected_failure = name in (
        "token-invalid-duration",
        "secrets-refused",
        "invalid-project",
        "missing-project",
    )
    assert (result["returncode"] != 0) == expected_failure, result
    requests = result["requests"]
    if name == "token-invalid-duration":
        assert not requests
    elif name == "invalid-project":
        assert len(requests) == 2
        assert requests[-1]["path"].endswith("not-a-project-uuid")
        assert "Fixture project does not exist" in result["stderr"]
        assert "Compiling:" not in result["stdout"]
    elif name == "missing-project":
        assert len(requests) == 2
        assert requests[-1]["path"].endswith(PROJECT_ID)
        assert "Fixture project does not exist" in result["stderr"]
        assert "Compiling:" not in result["stdout"]
    elif name == "secrets-refused":
        assert not result["stdout"].strip()
        assert "Fixture request is forbidden" in result["stderr"]
    elif name == "secrets-human":
        assert "Updated 2 secrets" in result["stdout"] + result["stderr"]
        assert "Not rebooting" in result["stdout"] + result["stderr"]
    elif name == "secrets-empty-list":
        assert "This app has no secrets" in result["stdout"]
    else:
        document = json.loads(result["stdout"])
        result["document"] = document
        if name.startswith("history"):
            if name == "history-empty":
                assert document == []
            else:
                assert document[0]["timestamp"] == TIMESTAMP
                assert document[0]["url"] == (
                    None if name == "history-nullable" else "https://qa.example.test"
                )
                assert document[0]["vm type"] == (
                    None if name == "history-nullable" else "Two cores / 4 GB"
                )
                assert document[0]["description"] == (
                    "" if name == "history-nullable" else "Promoted release"
                )
        elif name.startswith("inspect"):
            assert document["id"] == APP_ID
            if name == "inspect-nullable":
                assert document["latest_deployment"] is None
                assert document["backend_url"] is None
            else:
                nested = document["latest_deployment"]
                assert nested["timestamp"] == TIMESTAMP
                assert nested["persist"] is True
                assert nested["vm_type_name"] == "Two cores / 4 GB"
                assert "created_at" not in nested
                assert "persistent" not in nested
        elif name.startswith("token"):
            assert document["name"] == "server-renamed-token"
            assert document["expires_at"] == (
                None if name == "token-nullable" else "2026-10-12T12:34:56+00:00"
            )
            assert requests[-1]["body"] == {"name": "requested-token", "expiration": 90}
        elif name.startswith("secrets"):
            expected = (
                ["EMPTY", "FILE_ONLY"]
                if name == "secrets-envfile"
                else ["ALPHA", "EMPTY", "EQUALS"]
            )
            assert document == {
                "app_id": APP_ID,
                "updated": expected,
                "rebooted": name == "secrets-json",
            }
            sent = requests[-1]["body"]["secrets"]
            assert sorted(sent) == expected
            assert sent["EMPTY"] == ""
        elif name.startswith("permissions"):
            assert document == (
                []
                if name == "permissions-nullable"
                else ["can_deploy", "can_view_secret_keys"]
            )
    if name.startswith("secrets"):
        for value in SECRET_VALUES:
            assert value not in result["stdout"] + result["stderr"], result


def main() -> None:
    """Run independent local CLI scenarios and preserve every result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deploy-app", type=Path, required=True)
    args = parser.parse_args()
    assert "/private/tmp/" in str(reflex.__file__)
    assert "/site-packages/" in str(reflex.__file__)
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockAPI)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        with tempfile.TemporaryDirectory(
            prefix="reflex-hosting-extended-", dir="/private/tmp"
        ) as temporary:
            root = Path(temporary)
            credentials = root / "hosting.json"
            credentials.write_text(json.dumps({"access_token": "stored-fixture-token"}))
            envfile = root / ".env"
            envfile.write_text("FILE_ONLY=file-only-value\nEMPTY=\nBARE_KEY\n")
            settings = {
                "REFLEX_CLOUD_BACKEND_URL": f"http://127.0.0.1:{server.server_port}",
                "REFLEX_ACCESS_TOKEN": "supplied-fixture-token",
                "TEST_HOSTING_CONFIG": str(credentials),
                "NO_PROXY": "localhost,127.0.0.1",
                "no_proxy": "localhost,127.0.0.1",
                "REFLEX_TELEMETRY_ENABLED": "false",
                "REFLEX_CHECK_LATEST_VERSION": "false",
                "REFLEX_DIR": "/private/tmp/reflex-prerelease-components-20261005/runtime",
                "UV_CACHE_DIR": "/private/tmp/reflex-prerelease-components-20261005/uv-cache",
            }
            cases = []
            for name in ("history", "inspect"):
                cases.extend(
                    (
                        f"{name}-{scenario}",
                        scenario,
                        ["cloud", "apps", name, APP_ID, "--json", "--no-interactive"],
                    )
                    for scenario in ("full", "nullable")
                )
            cases.extend([
                (
                    "history-empty",
                    "empty",
                    ["cloud", "apps", "history", APP_ID, "--json", "--no-interactive"],
                ),
                (
                    "token-full",
                    "full",
                    [
                        "cloud",
                        "create-token",
                        "requested-token",
                        "--duration",
                        "90",
                        "--json",
                        "--no-interactive",
                    ],
                ),
                (
                    "token-nullable",
                    "nullable",
                    [
                        "cloud",
                        "create-token",
                        "requested-token",
                        "--json",
                        "--no-interactive",
                    ],
                ),
                (
                    "token-invalid-duration",
                    "full",
                    [
                        "cloud",
                        "create-token",
                        "requested-token",
                        "--duration",
                        "0",
                        "--json",
                        "--no-interactive",
                    ],
                ),
                (
                    "secrets-json",
                    "full",
                    [
                        "cloud",
                        "secrets",
                        "update",
                        APP_ID,
                        "--env",
                        "ALPHA=sentinel-only-for-fixture",
                        "--env",
                        "EQUALS=fixture=a=b",
                        "--env",
                        "EMPTY=",
                        "--reboot",
                        "--json",
                        "--loglevel",
                        "debug",
                        "--no-interactive",
                    ],
                ),
                (
                    "secrets-envfile",
                    "full",
                    [
                        "cloud",
                        "secrets",
                        "update",
                        APP_ID,
                        "--envfile",
                        str(envfile),
                        "--env",
                        "IGNORED=ignored-cli-value",
                        "--no-reboot",
                        "--json",
                        "--loglevel",
                        "debug",
                        "--no-interactive",
                    ],
                ),
                (
                    "secrets-human",
                    "full",
                    [
                        "cloud",
                        "secrets",
                        "update",
                        APP_ID,
                        "--env",
                        "ALPHA=sentinel-only-for-fixture",
                        "--env",
                        "EMPTY=",
                        "--no-reboot",
                        "--loglevel",
                        "debug",
                        "--no-interactive",
                    ],
                ),
                (
                    "secrets-refused",
                    "refused",
                    [
                        "cloud",
                        "secrets",
                        "update",
                        APP_ID,
                        "--env",
                        "ALPHA=sentinel-only-for-fixture",
                        "--json",
                        "--loglevel",
                        "debug",
                        "--no-interactive",
                    ],
                ),
                (
                    "secrets-empty-list",
                    "empty",
                    ["cloud", "secrets", "list", APP_ID, "--no-interactive"],
                ),
                (
                    "permissions-full",
                    "full",
                    [
                        "cloud",
                        "project",
                        "role-permissions",
                        ROLE_ID,
                        "--project-id",
                        PROJECT_ID,
                        "--json",
                        "--no-interactive",
                    ],
                ),
                (
                    "permissions-nullable",
                    "nullable",
                    [
                        "cloud",
                        "project",
                        "role-permissions",
                        ROLE_ID,
                        "--project-id",
                        PROJECT_ID,
                        "--json",
                        "--no-interactive",
                    ],
                ),
                (
                    "invalid-project",
                    "full",
                    [
                        "deploy",
                        "--app-name",
                        "qa-app",
                        "--project",
                        "not-a-project-uuid",
                        "--no-interactive",
                    ],
                ),
                (
                    "missing-project",
                    "full",
                    [
                        "deploy",
                        "--app-name",
                        "qa-app",
                        "--project",
                        " {22222222-2222-4222-8222-222222222222} ",
                        "--no-interactive",
                    ],
                ),
            ])
            for name, scenario, command in cases:
                server.scenario = scenario
                server.requests.clear()
                result = invoke(
                    command,
                    args.deploy_app if name.endswith("project") else root,
                    settings,
                )
                result.update(
                    name=name,
                    scenario=scenario,
                    requests=copy.deepcopy(server.requests),
                )
                try:
                    verify(name, result)
                    assert (
                        json.loads(credentials.read_text())["access_token"]
                        == "stored-fixture-token"
                    )
                    result["status"] = "passed"
                except Exception as error:
                    result.update(
                        status="failed",
                        error=str(error),
                        traceback=traceback.format_exc(),
                    )
                results.append(result)
                print(  # noqa: T201
                    json.dumps({
                        "name": name,
                        "status": result["status"],
                        "returncode": result["returncode"],
                    }),
                    flush=True,
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    provenance = {
        "executable": sys.executable,
        "reflex": reflex.__file__,
        "reflex_cli": reflex_cli.__file__,
        "versions": {
            name: importlib.metadata.version(name)
            for name in (
                "reflex",
                "reflex-base",
                "reflex-hosting-cli",
                "reflex-build-sdk",
                "python-dotenv",
            )
        },
        "nonlocal_connections": "blocked by audit hook",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"provenance": provenance, "results": results}, indent=2) + "\n"
    )
    if any(item["status"] != "passed" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
