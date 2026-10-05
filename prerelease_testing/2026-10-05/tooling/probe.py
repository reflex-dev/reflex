"""Exercise published release/docgen tools and cloud CLI against a local API."""

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import reflex
import yaml
from reflex_docgen.markdown import parse_document

UV = os.environ.get("QA_UV") or shutil.which("uv") or "/Users/masenf/.local/bin/uv"
APP_ID = "11111111-1111-4111-8111-111111111111"


def run(*command: str, cwd: Path, env: dict | None = None) -> dict:
    """Run a published command in the current isolated environment.

    Args:
        *command: Command and arguments.
        cwd: Neutral fixture directory.
        env: Additional environment settings.

    Returns:
        Captured command result.
    """
    settings = dict(
        os.environ,
        REFLEX_TELEMETRY_ENABLED="false",
        UV_CACHE_DIR="/private/tmp/reflex-pre-uv-cache",
        **(env or {}),
    )
    settings.pop("PYTHONPATH", None)
    process = subprocess.run(
        [UV, "run", "--no-project", "--python", sys.executable, *command],
        cwd=cwd,
        env=settings,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "args": list(command),
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


class MockAPI(BaseHTTPRequestHandler):
    """Serve deterministic API success and refusal responses over real HTTP."""

    def log_message(self, *args) -> None:
        """Keep HTTP fixture noise out of the result stream.

        Args:
            *args: Standard HTTP server log arguments.
        """

    def do_GET(self) -> None:
        """Handle a fixture request."""
        self.respond()

    def do_POST(self) -> None:
        """Handle a fixture request."""
        self.respond()

    def do_DELETE(self) -> None:
        """Handle a fixture request."""
        self.respond()

    def respond(self) -> None:
        """Send fixture responses and capture method/path evidence."""
        path = urlsplit(self.path).path.removeprefix("/api/v1")
        self.server.requests.append({"method": self.command, "path": self.path})
        status = 200
        if path == "/authenticate/me":
            if self.server.scenario == "expired":
                status, body = 401, {"detail": "Token has expired"}
            else:
                body = {
                    "user_id": APP_ID,
                    "org_id": APP_ID,
                    "email": "qa@example.test",
                    "tier": "Free",
                }
        elif self.server.scenario == "expires_after_auth":
            status, body = 401, {"detail": "Token has expired"}
        elif self.server.scenario == "refused":
            status, body = 403, {"detail": "Fixture policy refuses this request"}
        elif self.server.scenario == "missing":
            status, body = 404, {"detail": "Fixture app was not found"}
        elif path.endswith(("/start", "/stop")):
            body = {"message": "Server sentence must not become CLI result"}
        elif path.endswith("/logsv2"):
            second = "cursor=" in self.path
            body = [
                [
                    {
                        "ns": 1791203696000000000,
                        "name": "qa-app",
                        "timestamp": "2026-10-05T12:34:56Z",
                        "message": "second" if second else "first",
                    }
                ],
                None if second else "next-page",
            ]
        else:
            body = []
        content = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def release_probes(root: Path) -> list[dict]:
    """Generate real release workflows at and beyond the input boundary.

    Args:
        root: Disposable directory.

    Returns:
        Workflow-generation results.
    """
    results = []
    for count in (19, 20, 24, 25):
        fixture = root / f"release-{count}"
        fixture.mkdir()
        (fixture / "pyproject.toml").write_text(
            '[tool.reflex-release]\npackages-dir = "packages"\n'
        )
        for index in range(count):
            package = fixture / "packages" / f"sample-{index:02}"
            package.mkdir(parents=True)
            (package / "pyproject.toml").write_text(
                f'[project]\nname = "sample-{index:02}"\nversion = "1.0.0"\n'
            )
        result = run("reflex-release", "--root", str(fixture), "init", cwd=root)
        assert result["returncode"] == 0, result
        workflow = yaml.load(
            (fixture / ".github/workflows/dispatch_release.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        inputs = workflow["on"]["workflow_dispatch"]["inputs"]
        boolean = [name for name, item in inputs.items() if item["type"] == "boolean"]
        assert len(boolean) == (count if count <= 24 else 0), inputs
        assert len(inputs) <= 25, inputs
        checked = run(
            "reflex-release", "--root", str(fixture), "sync", "--check", cwd=root
        )
        assert checked["returncode"] == 0, checked
        results.append(
            {
                "package_count": count,
                "input_count": len(inputs),
                "checkbox_count": len(boolean),
                "generate": result,
                "check": checked,
            }
        )
    return results


def docgen_probes() -> list[dict]:
    """Parse realistic BOM, whitespace and CRLF documentation inputs.

    Returns:
        Parsed metadata and content evidence.
    """
    results = []
    for prefix, newline in (
        ("", "\n"),
        ("\ufeff", "\n"),
        (" \n\t", "\r\n"),
        ("\ufeff \r\n", "\r\n"),
    ):
        source = prefix + newline.join(
            (
                "---",
                "title: Metadata title",
                "description: SEO description",
                "image: /social.png",
                "---",
                "# Visible heading",
                "",
                "Visible body",
            )
        )
        document = parse_document(source)
        assert document.frontmatter.title == "Metadata title", document
        assert document.frontmatter.description == "SEO description", document
        rendered = repr(document.blocks)
        assert "Metadata title" not in rendered and "Visible heading" in rendered, (
            rendered
        )
        results.append(
            {
                "prefix": repr(prefix),
                "newline": repr(newline),
                "document": repr(document),
            }
        )
    return results


def hosting_probes(root: Path) -> list[dict]:
    """Drive installed cloud commands against a disposable HTTP service.

    Args:
        root: Disposable fixture directory.

    Returns:
        CLI outputs, assertions and HTTP requests.
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockAPI)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = root / "hosting.json"
    config.write_text(json.dumps({"access_token": "stored-fixture-token"}))
    settings = {
        "REFLEX_CLOUD_BACKEND_URL": f"http://127.0.0.1:{server.server_port}",
        "REFLEX_ACCESS_TOKEN": "supplied-fixture-token",
        "TEST_HOSTING_CONFIG": str(config),
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
    }
    results = []
    cases = [
        ("success", ["apps", "start", APP_ID]),
        ("success", ["apps", "stop", APP_ID]),
        ("refused", ["apps", "start", APP_ID]),
        ("refused", ["apps", "stop", APP_ID]),
        ("refused", ["vmtypes"]),
        ("refused", ["regions"]),
        ("missing", ["apps", "delete", APP_ID]),
        ("expired", ["apps", "list"]),
        ("expires_after_auth", ["apps", "stop", APP_ID]),
        ("success", ["apps", "logs", APP_ID]),
    ]
    try:
        for scenario, args in cases:
            server.scenario = scenario
            server.requests.clear()
            options = ["--json"]
            if args[0] == "apps":
                options.append("--no-interactive")
            result = run(
                "python",
                str(Path(__file__).with_name("cli_entry.py")),
                "cloud",
                *args,
                *options,
                cwd=root,
                env=settings,
            )
            result.update(scenario=scenario, requests=list(server.requests))
            assert server.requests, result
            if args[0] == "apps" and scenario != "expired":
                assert len(server.requests) >= 2, result
            expected_success = scenario == "success"
            assert (result["returncode"] == 0) == expected_success, result
            if expected_success:
                document = json.loads(result["stdout"])
                if args[1] == "logs":
                    assert [entry["message"] for entry in document["entries"]] == [
                        "first",
                        "second",
                    ], document
                    assert document["cursor"] is None, document
            elif scenario != "missing":
                assert not result["stdout"].strip(), result
            if scenario in ("expired", "expires_after_auth"):
                result["login_hint_present"] = "reflex login" in result["stderr"]
                if scenario == "expires_after_auth":
                    assert result["login_hint_present"], result
                assert not any(
                    "request" in request["path"] for request in server.requests
                ), result
            assert (
                json.loads(config.read_text())["access_token"] == "stored-fixture-token"
            )
            results.append(result)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    return results


def main() -> None:
    """Run tool probes and save their reproducible evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert Path(reflex.__file__).is_relative_to(Path(sys.prefix)), reflex.__file__
    with tempfile.TemporaryDirectory(prefix="reflex-tool-fixtures-") as scratch:
        root = Path(scratch)
        results = {
            "provenance": {
                "python": sys.executable,
                "reflex": reflex.__file__,
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in (
                        "reflex",
                        "reflex-base",
                        "reflex-docgen",
                        "reflex-hosting-cli",
                        "reflex-release",
                    )
                },
            },
            "release": release_probes(root),
            "docgen": docgen_probes(),
            "hosting": hosting_probes(root),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(
        json.dumps({key: len(results[key]) for key in ("release", "docgen", "hosting")})
    )


if __name__ == "__main__":
    main()
