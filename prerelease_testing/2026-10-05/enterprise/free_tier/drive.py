"""Test public enterprise CLI badge guards against a disposable HTTP account API."""

import hashlib
import importlib.metadata
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import zipfile
from functools import partial
from html.parser import HTMLParser
from http.server import (
    BaseHTTPRequestHandler,
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path
from urllib.parse import urlsplit

import reflex_enterprise
from playwright.sync_api import sync_playwright

import reflex

UV = "/Users/masenf/.local/bin/uv"
FIXTURE_TOKEN = "local-free-tier-fixture-token"
APP_URL = "http://127.0.0.1:3131/"
ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"


class AccountAPI(BaseHTTPRequestHandler):
    """Provide only the real hosting SDK's account identity endpoint."""

    def do_GET(self) -> None:
        """Validate a fictional credential and return the selected local tier."""
        self.respond()

    def do_POST(self) -> None:
        """Respond to the SDK's real POST identity-validation request."""
        self.respond()

    def respond(self) -> None:
        """Record the wire request and return a local identity response."""
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length)) if length else None
        authorized = self.headers.get("X-API-TOKEN") == FIXTURE_TOKEN
        status = 200
        if path.removeprefix("/api/v1") != "/authenticate/me":
            status, response = 404, {"detail": "Unknown fixture route"}
        elif not authorized or self.server.tier == "Rejected":
            status, response = 401, {"detail": "Disposable token was rejected"}
        else:
            response = {
                "user_id": "11111111-1111-4111-8111-111111111111",
                "org_id": "22222222-2222-4222-8222-222222222222",
                "email": "badge-qa@example.test",
                "tier": self.server.tier,
            }
        self.server.requests.append({
            "case": self.server.case,
            "method": self.command,
            "path": path,
            "body": body,
            "sdk_token_present": bool(self.headers.get("X-API-TOKEN")),
            "only_fixture_credential": authorized,
            "response_tier": self.server.tier,
            "status": status,
        })
        payload = json.dumps(response).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Request-ID", "disposable-badge-fixture")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        """Suppress the HTTP server's routine console output.

        Args:
            format: Log message format.
            *args: Log formatting arguments.
        """


class VisibleText(HTMLParser):
    """Collect server-rendered text while excluding script/style contents."""

    def __init__(self) -> None:
        """Initialize text collection."""
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Track script/style nesting.

        Args:
            tag: HTML tag.
            attrs: Tag attributes.
        """
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        """Leave script/style nesting.

        Args:
            tag: HTML tag.
        """
        if tag in {"script", "style"}:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        """Collect visible text.

        Args:
            data: HTML text segment.
        """
        if not self.hidden:
            self.parts.append(data)


def stop_process(process: subprocess.Popen) -> None:
    """Stop only the owned CLI process group and wait for cleanup.

    Args:
        process: Owned CLI subprocess.
    """
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)


def read_page() -> str | None:
    """Read the loopback production page if ready.

    Returns:
        HTML containing the fixture heading, or None before readiness.
    """
    try:
        with urllib.request.urlopen(APP_URL, timeout=1) as response:
            html = response.read().decode()
    except (urllib.error.URLError, TimeoutError):
        return None
    return html if "Badge policy QA" in html else None


def inspect_browser(browser, url: str, name: str, badge: bool, event: bool) -> dict:
    """Verify rendered badge visibility and optional backend events.

    Args:
        browser: Published Playwright browser.
        url: Local production or static export URL.
        name: Case name.
        badge: Expected visible badge.
        event: Whether a running backend should process a counter event.

    Returns:
        Browser observations and diagnostic messages.
    """
    context = browser.new_context()
    page = context.new_page()
    errors, console = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: console.append({"type": message.type, "text": message.text}),
    )
    try:
        page.goto(url, wait_until="networkidle")
        page.get_by_role("heading", name="Badge policy QA").wait_for()
        badge_visible = page.get_by_text("Built with Reflex", exact=True).is_visible()
        assert badge_visible is badge, (name, badge_visible, badge)
        if event:
            page.get_by_role("button", name="Increment", exact=True).click()
            page.locator("#count").filter(has_text="1").wait_for(timeout=10000)
        page.screenshot(path=ROOT / "screenshots" / f"{name}.png", full_page=True)
        result = {
            "badge_visible": badge_visible,
            "counter": page.locator("#count").inner_text(),
            "page_errors": errors,
            "console": console,
        }
        assert not errors, result
        return result
    finally:
        context.close()


def inspect_export(
    export_dir: Path, name: str, badge: bool, browser, render: bool
) -> dict:
    """Inspect the real frontend ZIP and optionally render it over local HTTP.

    Args:
        export_dir: Unique export destination.
        name: Case name.
        badge: Expected server-rendered badge.
        browser: Published Playwright browser.
        render: Whether to view the exported static app.

    Returns:
        Export archive and rendered badge observations.
    """
    archives = list(export_dir.glob("*.zip"))
    assert len(archives) == 1, archives
    archive = archives[0]
    with zipfile.ZipFile(archive) as bundle:
        html = bundle.read("index.html").decode()
        members = bundle.namelist()
        static_dir = export_dir / "rendered"
        if render:
            bundle.extractall(static_dir)
    parser = VisibleText()
    parser.feed(html)
    rendered_text = re.sub(r"\s+", " ", " ".join(parser.parts))
    badge_in_html = "Built with Reflex" in rendered_text
    assert badge_in_html is badge, (name, rendered_text)
    (ROOT / "logs" / f"{name}-index.html").write_text(html)
    result = {
        "archive": archive.name,
        "bytes": archive.stat().st_size,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "member_count": len(members),
        "badge_in_server_html": badge_in_html,
        "visible_server_text": rendered_text,
    }
    if render:
        static_server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(SimpleHTTPRequestHandler, directory=str(static_dir)),
        )
        thread = threading.Thread(target=static_server.serve_forever, daemon=True)
        thread.start()
        try:
            result["browser"] = inspect_browser(
                browser,
                f"http://127.0.0.1:{static_server.server_port}/",
                name,
                badge,
                False,
            )
        finally:
            static_server.shutdown()
            static_server.server_close()
            thread.join()
    return result


def run_case(
    server,
    browser,
    temporary: Path,
    name: str,
    tier: str,
    badge: bool,
    command: list[str],
    denied: bool = False,
    render: bool = False,
) -> dict:
    """Run one unmodified public CLI command against the HTTP account fixture.

    Args:
        server: Disposable account API.
        browser: Published Playwright browser.
        temporary: Disposable credential/output directory.
        name: Case name.
        tier: HTTP response tier, or Rejected for a 401.
        badge: Requested configuration badge value.
        command: Public CLI arguments.
        denied: Whether authentication should prevent output/server startup.
        render: Whether an exported ZIP should also be viewed in a browser.

    Returns:
        CLI, HTTP, audit, and browser/export evidence.
    """
    server.tier, server.case = tier, name
    start = len(server.requests)
    credentials = temporary / f"{name}-hosting.json"
    credentials.write_text(json.dumps({"access_token": FIXTURE_TOKEN}))
    audit_path = ROOT / "logs" / f"{name}-network.jsonl"
    audit_path.unlink(missing_ok=True)
    context_path = ROOT / "logs" / f"{name}-context.jsonl"
    context_path.unlink(missing_ok=True)
    settings = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "CI",
        "APP_HARNESS_FLAG",
        "REFLEX_ACCESS_TOKEN",
        "REFLEX_APP_HARNESS",
        "REFLEX_SKIP_COMPILE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        settings.pop(key, None)
    settings.update({
        "QA_BADGE": str(badge).lower(),
        "TEST_HOSTING_CONFIG": str(credentials),
        "TEST_NETWORK_AUDIT": str(audit_path),
        "TEST_CONTEXT_AUDIT": str(context_path),
        "REFLEX_CLOUD_BACKEND_URL": f"http://127.0.0.1:{server.server_port}",
        "REFLEX_CLOUD_URL": f"http://127.0.0.1:{server.server_port}",
        "REFLEX_DIR": "/private/tmp/reflex-enterprise-free-tier-runtime-20261005",
        "REFLEX_TELEMETRY_ENABLED": "false",
        "REFLEX_CHECK_LATEST_VERSION": "false",
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org",
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
        "UV_CACHE_DIR": "/private/tmp/reflex-enterprise-uv-cache",
        "PATH": "/Users/masenf/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    })
    export_dir = temporary / name
    export_dir.mkdir()
    if command[0] == "export":
        command += ["--frontend-only", "--zip-dest-dir", str(export_dir)]
    argv = [
        UV,
        "--no-config",
        "run",
        "--no-project",
        "--python",
        sys.executable,
        "python",
        "cli_entry.py",
        *command,
        "--loglevel",
        "debug",
    ]
    result = {
        "name": name,
        "tier": tier,
        "badge_requested": badge,
        "ci": False,
        "command": argv,
        "credential_file_redirected": True,
    }
    log_path = ROOT / "logs" / f"{name}-cli.log"
    with log_path.open("w") as output:
        process = subprocess.Popen(
            argv,
            cwd=APP,
            env=settings,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            if command[0] == "run" and not denied:
                deadline = time.monotonic() + 90
                html = None
                while process.poll() is None and time.monotonic() < deadline:
                    html = read_page()
                    if html:
                        break
                    time.sleep(0.2)
                assert html, log_path.read_text()
                result["browser"] = inspect_browser(browser, APP_URL, name, True, True)
            else:
                process.wait(timeout=120)
                result["exit_code"] = process.returncode
                if denied:
                    assert not list(export_dir.glob("*.zip"))
                else:
                    assert process.returncode == 0, log_path.read_text()
                    result["export"] = inspect_export(
                        export_dir, name, tier == "Free" or badge, browser, render
                    )
        finally:
            stop_process(process)
    text = log_path.read_text()
    result["badge_restriction_warning"] = (
        "show_built_with_reflex" in text and "restricted" in text
    )
    result["denied_message"] = "must be logged in" in text
    result["http_requests"] = server.requests[start:]
    assert result["http_requests"], result
    assert all(
        request["only_fixture_credential"] for request in result["http_requests"]
    ), result
    if denied:
        assert result["denied_message"], text
    if tier == "Free" and not badge:
        assert result["badge_restriction_warning"], text
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert audit and all(entry["allowed"] for entry in audit), audit
    result["python_connections"] = audit
    contexts = [json.loads(line) for line in context_path.read_text().splitlines()]
    assert contexts and all(
        not item["ci_env_present"]
        and item["ci_parser_value"] is False
        and not item["app_harness_env_present"]
        and item["offline_distribution"] is False
        for item in contexts
    ), contexts
    result["guard_contexts"] = contexts
    result["result"] = "PASS"
    return result


def main() -> None:
    """Run the Free-tier/public-CLI matrix and persist reproducible evidence."""
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "screenshots").mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), AccountAPI)
    server.requests, server.tier, server.case = [], "Free", "initial"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    cases = [
        (
            "free-prod-badge-on",
            "Free",
            True,
            [
                "run",
                "--env",
                "prod",
                "--frontend-port",
                "3131",
                "--backend-port",
                "3131",
                "--backend-host",
                "127.0.0.1",
            ],
            False,
            False,
        ),
        (
            "free-prod-badge-off",
            "Free",
            False,
            [
                "run",
                "--env",
                "prod",
                "--frontend-port",
                "3131",
                "--backend-port",
                "3131",
                "--backend-host",
                "127.0.0.1",
            ],
            False,
            False,
        ),
        (
            "free-export-prod-badge-on",
            "Free",
            True,
            ["export", "--env", "prod"],
            False,
            False,
        ),
        (
            "free-export-prod-badge-off",
            "Free",
            False,
            ["export", "--env", "prod"],
            False,
            False,
        ),
        (
            "free-export-dev-badge-on",
            "Free",
            True,
            ["export", "--env", "dev"],
            False,
            True,
        ),
        (
            "paid-export-prod-badge-off",
            "Enterprise",
            False,
            ["export", "--env", "prod"],
            False,
            False,
        ),
        (
            "rejected-prod",
            "Rejected",
            True,
            [
                "run",
                "--env",
                "prod",
                "--frontend-port",
                "3131",
                "--backend-port",
                "3131",
                "--backend-host",
                "127.0.0.1",
            ],
            True,
            False,
        ),
        ("rejected-export", "Rejected", True, ["export", "--env", "prod"], True, False),
    ]
    provenance = {
        "reflex_origin": reflex.__file__,
        "enterprise_origin": reflex_enterprise.__file__,
        "python": sys.executable,
        "packages": {
            name: importlib.metadata.version(name)
            for name in (
                "reflex",
                "reflex-base",
                "reflex-enterprise",
                "reflex-hosting-cli",
                "playwright",
            )
        },
        "api_bind": "127.0.0.1",
        "ci_bypass": False,
        "tier_functions_patched": False,
        "credential_configuration_only_redirected": True,
    }
    try:
        with (
            tempfile.TemporaryDirectory(
                prefix="reflex-free-tier-", dir="/private/tmp"
            ) as temp,
            sync_playwright() as playwright,
        ):
            browser = playwright.chromium.launch(headless=True)
            try:
                for case in cases:
                    try:
                        result = run_case(server, browser, Path(temp), *case)
                    except Exception:
                        result = {
                            "name": case[0],
                            "result": "FAIL",
                            "traceback": traceback.format_exc(),
                        }
                    results.append(result)
                    (ROOT / "results.json").write_text(
                        json.dumps(
                            {
                                "provenance": provenance,
                                "results": results,
                                "api_requests": server.requests,
                            },
                            indent=2,
                        )
                        + "\n"
                    )
                    print(case[0], result["result"], flush=True)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert all(result["result"] == "PASS" for result in results), results


if __name__ == "__main__":
    main()
