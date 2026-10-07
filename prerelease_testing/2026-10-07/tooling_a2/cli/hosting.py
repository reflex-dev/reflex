"""Exercise installed CLI and SDK contracts against one owned local HTTP origin."""

import argparse
import asyncio
import copy
import importlib.metadata
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fixtures import APP_ID, PROJECT_ID, ROLE_ID, app_document, deployment, verify
from guard import install

ROOT = Path(__file__).parent
CURSOR = "next page+/=?&x"


class API(BaseHTTPRequestHandler):
    """Return realistic response models while retaining every local request."""

    def log_message(self, *args) -> None:
        """Suppress HTTP access noise.

        Args:
            *args: Standard server log arguments.
        """

    def do_GET(self) -> None:
        """Handle an SDK GET request."""
        self.respond()

    def do_POST(self) -> None:
        """Handle an SDK POST request."""
        self.respond()

    def do_DELETE(self) -> None:
        """Handle an SDK DELETE request."""
        self.respond()

    def respond(self) -> None:
        """Record the actual wire request and emit the selected response."""
        parsed = urlsplit(self.path)
        path = parsed.path.removeprefix("/api/v1")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        request = {
            "method": self.command,
            "path": self.path,
            "host": self.headers.get("Host"),
            "authorization": self.headers.get("Authorization"),
            "api_token": self.headers.get("X-API-TOKEN"),
            "request_id": self.headers.get("X-Request-ID"),
            "body": json.loads(raw) if raw else None,
        }
        self.server.requests.append(request)
        scenario = self.server.scenario
        status, body = 200, []
        if path == "/__fixture__/health":
            body = {"fixture": "tooling-a2-owned", "port": self.server.server_port}
        elif scenario.startswith("sdk-status-"):
            status, body = (
                int(scenario.rsplit("-", 1)[1]),
                {"detail": "Fixture status boundary"},
            )
        elif scenario == "sdk-invalid-json":
            body = b"not-json"
        elif scenario == "sdk-invalid-model":
            body = {"id": "not-a-uuid"}
        elif path == "/authenticate/me":
            if scenario == "expired":
                status, body = 401, {"detail": "Token has expired"}
            else:
                body = {
                    "user_id": APP_ID,
                    "org_id": APP_ID,
                    "email": "qa@example.test",
                    "tier": "Enterprise",
                }
        elif scenario == "expires_after_auth":
            status, body = 401, {"detail": "Token has expired"}
        elif scenario == "refused":
            status, body = 403, {"detail": "Fixture request is forbidden"}
        elif scenario == "missing":
            status, body = 404, {"detail": "Fixture app was not found"}
        elif path.endswith(("/start", "/stop")):
            body = {"message": "Server sentence must not become CLI result"}
        elif path.endswith("/logsv2"):
            second = parse_qs(parsed.query).get("cursor") == [CURSOR]
            entry = {
                "ns": 1791203696000000000,
                "name": "qa-app",
                "timestamp": "2026-10-05T12:34:56Z",
                "message": "second" if second else "first",
            }
            body = (
                [[], CURSOR]
                if scenario == "empty-page"
                else [[entry], None if second else CURSOR]
            )
        elif path == f"/apps/{APP_ID}/history":
            record = deployment()
            if scenario == "nullable":
                record.update(
                    vm_type=None, url=None, description=None, can_rollback=False
                )
            body = [] if scenario == "empty" else [record]
        elif path == f"/apps/{APP_ID}":
            body = app_document()
            if scenario == "nullable":
                body.update(
                    latest_deployment=None,
                    has_deployments=False,
                    backend_url=None,
                    any_environment_live=False,
                )
        elif path == "/user/token/create":
            body = {
                "name": "server-renamed-token",
                "token": "created-fixture-token",
                "expiration": None
                if scenario == "nullable"
                else "2026-10-12T12:34:56+00:00",
            }
        elif path == f"/apps/{APP_ID}/secrets":
            body = (
                [] if self.command == "GET" else {"message": "Fixture secrets accepted"}
            )
        elif path == f"/project/{PROJECT_ID}/role/{ROLE_ID}":
            body = (
                None
                if scenario == "nullable"
                else [
                    {"name": "can_deploy", "id": 1},
                    {"name": "can_view_secret_keys", "id": 2},
                ]
            )
        else:
            status, body = 500, {"detail": "Unexpected fixture endpoint"}
        encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
        request.update(
            response_status=status,
            response_body=body.decode() if isinstance(body, bytes) else body,
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("X-Tooling-Fixture", "owned-localhost")
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    """Run sequential public API cases and preserve successful and failed evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    assert "/envs/tooling-cli-" in sys.prefix, sys.prefix
    args.scratch.mkdir(parents=True, exist_ok=True)
    credentials = args.scratch / "hosting.json"
    credentials.write_text(json.dumps({"access_token": "stored-fixture-token"}))
    envfile = args.scratch / ".env"
    envfile.write_text("FILE_ONLY=file-only-value\nEMPTY=\nBARE_KEY\n")
    os.environ.update(
        TOOLING_FIXTURE_ROOT=str(args.scratch),
        TOOLING_FIXTURE_PORT="8580",
        TOOLING_EXPECT_ENV=sys.prefix,
        TEST_HOSTING_CONFIG=str(credentials),
        REFLEX_DIR=str(args.scratch / "runtime"),
        REFLEX_CLOUD_BACKEND_URL="http://127.0.0.1:8580",
        REFLEX_BUILD_BACKEND_URL="http://127.0.0.1:8580",
        REFLEX_ACCESS_TOKEN="supplied-fixture-token",
        REFLEX_TELEMETRY_ENABLED="false",
        REFLEX_CHECK_LATEST_VERSION="false",
        NO_PROXY="127.0.0.1",
        no_proxy="127.0.0.1",
    )
    os.environ.pop("PYTHONPATH", None)
    install()
    import reflex
    import reflex_build_sdk
    from reflex_build_sdk import AsyncReflexBuild, ReflexBuild

    for module in (reflex, reflex_build_sdk):
        assert Path(module.__file__).is_relative_to(Path(sys.prefix)), module.__file__
    server = ThreadingHTTPServer(("127.0.0.1", 8580), API)
    server.requests, server.scenario = [], "success"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = {
        "provenance": {
            "python": sys.executable,
            "modules": {m.__name__: m.__file__ for m in (reflex, reflex_build_sdk)},
            "versions": {
                p: importlib.metadata.version(p)
                for p in (
                    "reflex",
                    "reflex-base",
                    "reflex-hosting-cli",
                    "reflex-build-sdk",
                    "reflex-release",
                    "reflex-docgen",
                )
            },
        },
        "origin": "http://127.0.0.1:8580",
        "cases": [],
    }

    def record(name, scenario, function):
        """Retain each case even when its contract fails.

        Args:
            name: Human-readable case identifier.
            scenario: Fixture response selection.
            function: Case callable returning evidence.
        """
        server.scenario, server.requests = scenario, []
        entry = {"name": name, "scenario": scenario}
        results.pop("last_cli_attempt", None)
        try:
            entry.update(function())
            expected_token = (
                "sdk-fixture-token"
                if name.startswith("sdk-") or name == "owned-origin-preflight"
                else "stored-fixture-token"
                if name == "cli-stored-token"
                else "supplied-fixture-token"
            )
            for request in server.requests:
                if request["path"] == "/__fixture__/health" or name in (
                    "cli-refused-vmtypes",
                    "cli-refused-regions",
                ):
                    continue
                assert request["api_token"] == expected_token, request
            entry["pass"] = True
        except Exception as error:
            entry.update(results.pop("last_cli_attempt", {}))
            entry.update(
                {
                    "pass": False,
                    "error": repr(error),
                    "traceback": traceback.format_exc(),
                }
            )
        entry["requests"] = copy.deepcopy(server.requests)
        results["cases"].append(entry)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n")
        print(name, entry["pass"], flush=True)

    def cli_case(command, prior_name=None, expected_success=True):
        """Invoke the public CLI in a child with isolated fixture credentials.

        Args:
            command: Public command arguments.
            prior_name: Optional prior scenario oracle.
            expected_success: Expected zero exit status.

        Returns:
            Complete subprocess outputs and optional parsed JSON.
        """
        invocation = [
            shutil.which("uv"),
            "--no-config",
            "run",
            "--no-project",
            "--python",
            sys.executable,
            "python",
            str(ROOT / "cli_entry.py"),
            *command,
        ]
        child = subprocess.run(
            invocation,
            cwd=args.scratch,
            env=dict(os.environ),
            capture_output=True,
            text=True,
            timeout=45,
        )
        row = {
            "args": command,
            "command": invocation,
            "returncode": child.returncode,
            "stdout": child.stdout,
            "stderr": child.stderr,
            "requests": copy.deepcopy(server.requests),
        }
        # Save outputs before assertions so failures retain both streams.
        results["last_cli_attempt"] = row
        if prior_name:
            verify(prior_name, row)
        else:
            assert (child.returncode == 0) == expected_success, row
            if expected_success:
                row["document"] = json.loads(child.stdout)
                if command[1:3] in (["apps", "start"], ["apps", "stop"]):
                    action = command[2]
                    assert row["document"] == {
                        "app_id": APP_ID,
                        action + ("ped" if action == "stop" else "ed"): True,
                        "message": f"app {action}"
                        + ("ped" if action == "stop" else "ed"),
                    }, row
                if command[1:3] == ["apps", "logs"]:
                    messages = [
                        entry["message"] for entry in row["document"]["entries"]
                    ]
                    assert messages == (
                        [] if server.scenario == "empty-page" else ["first", "second"]
                    ), row
                    assert (
                        row["document"]["cursor"] is None
                        and row["document"]["error"] is None
                    ), row
            elif server.scenario != "missing":
                assert not child.stdout.strip(), row
            if server.scenario in (
                "refused",
                "missing",
                "expired",
                "expires_after_auth",
            ):
                expected_status = {
                    "refused": 403,
                    "missing": 404,
                    "expired": 401,
                    "expires_after_auth": 401,
                }[server.scenario]
                assert server.requests[-1]["response_status"] == expected_status, row
            if server.scenario == "missing":
                assert json.loads(child.stdout)["deleted"] is False, row
            if server.scenario == "expired":
                assert len(server.requests) == 1, row
                row["login_hint_present"] = "reflex login" in child.stderr
            if server.scenario == "expires_after_auth":
                assert len(server.requests) == 2 and "reflex login" in child.stderr, row
        assert (
            json.loads(credentials.read_text())["access_token"]
            == "stored-fixture-token"
        )
        assert all(r["host"] == "127.0.0.1:8580" for r in server.requests)
        return row

    try:

        def preflight():
            """Validate fixture ownership, SDK origin, and connection guard.

            Returns:
                Origin and guard evidence.
            """
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                results["origin"] + "/__fixture__/health"
            ) as response:
                health = json.load(response)
                assert response.headers["X-Tooling-Fixture"] == "owned-localhost"
            assert health == {"fixture": "tooling-a2-owned", "port": 8580}
            with ReflexBuild(
                token="sdk-fixture-token", base_url=results["origin"], max_retries=0
            ) as client:
                assert str(client.auth.me().user_id) == APP_ID
                assert client.base_url == results["origin"]
            try:
                with socket.socket() as sock:
                    sock.connect(("203.0.113.1", 443))
            except PermissionError:
                return {"health": health, "nonlocal_guard": "blocked before connect"}
            raise AssertionError("Nonlocal socket guard failed")

        record("owned-origin-preflight", "success", preflight)
        assert results["cases"][0]["pass"], results["cases"][0]
        record(
            "cli-start-preflight",
            "success",
            lambda: cli_case(
                ["cloud", "apps", "start", APP_ID, "--json", "--no-interactive"]
            ),
        )
        if not args.preflight_only:

            def stored_token():
                """Verify the redirected stored token when no environment override exists.

                Returns:
                    Public CLI command evidence.
                """
                token = os.environ.pop("REFLEX_ACCESS_TOKEN")
                try:
                    return cli_case(
                        ["cloud", "apps", "stop", APP_ID, "--json", "--no-interactive"]
                    )
                finally:
                    os.environ["REFLEX_ACCESS_TOKEN"] = token

            record("cli-stored-token", "success", stored_token)

            def missing_token():
                """Require the public SDK to reject missing credentials before HTTP.

                Returns:
                    Typed exception evidence.
                """
                token = os.environ.pop("REFLEX_ACCESS_TOKEN")
                try:
                    with ReflexBuild(
                        base_url=results["origin"], max_retries=0
                    ) as client:
                        try:
                            client.apps.get(APP_ID)
                        except Exception as error:
                            assert (
                                type(error).__name__ == "MissingTokenError"
                                and not server.requests
                            ), repr(error)
                            return {
                                "exception_type": type(error).__name__,
                                "no_http_request": True,
                            }
                    raise AssertionError("SDK accepted missing credentials")
                finally:
                    os.environ["REFLEX_ACCESS_TOKEN"] = token

            record("sdk-missing-token", "success", missing_token)
            for prior in json.loads((ROOT / "prior-cases.json").read_text()):
                command = list(prior["args"])
                if "--envfile" in command:
                    command[command.index("--envfile") + 1] = str(envfile)
                record(
                    prior["name"],
                    prior["scenario"],
                    lambda c=command, n=prior["name"]: cli_case(c, n),
                )
            for scenario, command in [
                ("success", ["apps", "stop", APP_ID]),
                ("refused", ["apps", "start", APP_ID]),
                ("refused", ["apps", "stop", APP_ID]),
                ("refused", ["vmtypes"]),
                ("refused", ["regions"]),
                ("missing", ["apps", "delete", APP_ID]),
                ("expired", ["apps", "list"]),
                ("expires_after_auth", ["apps", "stop", APP_ID]),
                ("success", ["apps", "logs", APP_ID]),
                ("empty-page", ["apps", "logs", APP_ID]),
            ]:
                options = ["--json"] + (
                    ["--no-interactive"] if command[0] == "apps" else []
                )
                record(
                    "cli-" + scenario + "-" + "-".join(command[:2]),
                    scenario,
                    lambda c=command, o=options, s=scenario: cli_case(
                        ["cloud", *c, *o],
                        expected_success=s in ("success", "empty-page"),
                    ),
                )
            for status, expected in (
                (400, "BadRequestError"),
                (401, "AuthenticationError"),
                (403, "PermissionDeniedError"),
                (404, "NotFoundError"),
                (409, "ConflictError"),
                (422, "UnprocessableEntityError"),
                (429, "RateLimitError"),
                (500, "InternalServerError"),
            ):

                def error_case(expected=expected, status=status):
                    """Check the public SDK's typed HTTP error mapping.

                    Args:
                        expected: Required exception class name.
                        status: Required HTTP status.

                    Returns:
                        Exception metadata.
                    """
                    with ReflexBuild(
                        token="sdk-fixture-token",
                        base_url=results["origin"],
                        max_retries=0,
                    ) as client:
                        try:
                            client.apps.get(APP_ID)
                        except Exception as error:
                            assert type(error).__name__ == expected, repr(error)
                            assert (
                                error.status_code == status
                                and error.detail == "Fixture status boundary"
                            )
                            return {
                                "exception_type": type(error).__name__,
                                "status_code": error.status_code,
                                "detail": error.detail,
                            }
                    raise AssertionError("SDK accepted HTTP failure")

                record(f"sdk-http-{status}", f"sdk-status-{status}", error_case)
            for malformed in ("sdk-invalid-json", "sdk-invalid-model"):

                def malformed_case():
                    """Require a typed validation exception for malformed API data.

                    Returns:
                        The public exception type.
                    """
                    with ReflexBuild(
                        token="sdk-fixture-token",
                        base_url=results["origin"],
                        max_retries=0,
                    ) as client:
                        try:
                            client.apps.get(APP_ID)
                        except Exception as error:
                            assert (
                                type(error).__name__ == "APIResponseValidationError"
                            ), repr(error)
                            return {"exception_type": type(error).__name__}
                    raise AssertionError("SDK accepted malformed response")

                record(malformed, malformed, malformed_case)
            for engine in ("sync", "async"):

                def pages(engine=engine):
                    """Verify two real pages and exact escaped cursor round-tripping.

                    Args:
                        engine: Sync or async SDK facade.

                    Returns:
                        Ordered message evidence.
                    """

                    async def asynchronous():
                        """Read the same public pagination interface asynchronously.

                        Returns:
                            Ordered messages.
                        """
                        async with AsyncReflexBuild(
                            token="sdk-fixture-token",
                            base_url=results["origin"],
                            max_retries=0,
                        ) as client:
                            return [
                                entry.message
                                async for entry in client.apps.logs(
                                    APP_ID, search="café + /", page_size=50
                                )
                            ]

                    if engine == "async":
                        messages = asyncio.run(asynchronous())
                    else:
                        with ReflexBuild(
                            token="sdk-fixture-token",
                            base_url=results["origin"],
                            max_retries=0,
                        ) as client:
                            messages = [
                                entry.message
                                for entry in client.apps.logs(
                                    APP_ID, search="café + /", page_size=50
                                )
                            ]
                    assert messages == ["first", "second"], messages
                    assert len(server.requests) == 2
                    query = parse_qs(urlsplit(server.requests[1]["path"]).query)
                    assert query["cursor"] == [CURSOR] and query["search"] == [
                        "café + /"
                    ]
                    return {"messages": messages, "second_query": query}

                record(f"sdk-{engine}-pagination", "success", pages)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        results["cleanup"] = {
            "server_thread_alive": thread.is_alive(),
            "server_socket_fd": server.socket.fileno(),
        }
        results.pop("last_cli_attempt", None)
        args.output.write_text(json.dumps(results, indent=2) + "\n")
    raise SystemExit(int(any(not row["pass"] for row in results["cases"])))


if __name__ == "__main__":
    main()
