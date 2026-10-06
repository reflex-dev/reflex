"""Observe production MCP routing with published Reflex 0.9.12 and enterprise a3."""

import asyncio
import importlib.metadata
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
UV = "/Users/masenf/.local/bin/uv"
BASE = "http://127.0.0.1:3131"
TOKEN = "local-enterprise-a3-components-fixture-token"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "stable-routing-control", "version": "1"},
    },
}


def stop(process: subprocess.Popen | None) -> None:
    """Stop only an owned subprocess group.

    Args:
        process: The fixture or public CLI child process.
    """
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)


async def sdk_probe(path: str, token: str) -> dict:
    """Try the published SDK without hiding redirect or HTTP failures.

    Args:
        path: Bare or trailing-slash MCP route.
        token: A disposable anonymous token issued by this local app.

    Returns:
        Initialization/list-tools result and credential-free response metadata.
    """
    result = {"path": path, "responses": [], "passed": False}

    async def record_response(response: httpx.Response) -> None:
        """Record an SDK response without bearer or session credentials.

        Args:
            response: A completed SDK HTTP response.
        """
        result["responses"].append({
            "method": response.request.method,
            "url": str(response.request.url),
            "status": response.status_code,
            "location": response.headers.get("location"),
        })

    try:
        async with httpx.AsyncClient(
            headers={"Authorization": "Bearer " + token},
            follow_redirects=True,
            event_hooks={"response": [record_response]},
        ) as client:
            async with streamable_http_client(BASE + path, http_client=client) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    tools = await session.list_tools()
                    result.update(
                        passed=True,
                        protocol_version=initialized.protocolVersion,
                        tools=[tool.name for tool in tools.tools],
                    )
    except Exception:
        result["traceback"] = traceback.format_exc()
    return result


def browser_probe() -> dict:
    """Open the actual production app and retain browser diagnostics.

    Returns:
        Visible readiness and browser console/page/network observations.
    """
    result = {
        "console": [],
        "page_errors": [],
        "http_errors": [],
        "failed_requests": [],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on(
            "console",
            lambda message: result["console"].append({
                "type": message.type,
                "text": message.text,
                "location": message.location,
            }),
        )
        page.on("pageerror", lambda error: result["page_errors"].append(str(error)))
        page.on(
            "response",
            lambda response: (
                result["http_errors"].append({
                    "url": response.url,
                    "status": response.status,
                })
                if response.status >= 400
                else None
            ),
        )
        page.on(
            "requestfailed",
            lambda request: result["failed_requests"].append({
                "url": request.url,
                "failure": request.failure,
            }),
        )
        try:
            page.goto(BASE, wait_until="networkidle")
            expect(
                page.get_by_role("heading", name="MCP routing probe")
            ).to_be_visible()
            page.wait_for_timeout(1000)
            result.update(ready=True, body=page.locator("body").inner_text())
            page.screenshot(path=str(ROOT / "logs/browser.png"), full_page=True)
        except Exception:
            result.update(ready=False, traceback=traceback.format_exc())
        finally:
            result["browser_version"] = browser.version
            context.close()
            browser.close()
    return result


def main() -> None:
    """Run the public CLI control and always preserve observations and cleanup."""
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    settings = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "CI",
        "APP_HARNESS_FLAG",
        "REFLEX_APP_HARNESS",
        "REFLEX_SKIP_COMPILE",
        "REFLEX_ACCESS_TOKEN",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        settings.pop(key, None)
    assert "PYTHONPATH" not in os.environ
    versions = {
        name: importlib.metadata.version(name)
        for name in (
            "reflex",
            "reflex-base",
            "reflex-enterprise",
        )
    }
    assert versions == {
        "reflex": "0.9.12",
        "reflex-base": "0.9.12",
        "reflex-enterprise": "0.9.7a3",
    }, versions
    argv = [
        UV,
        "--no-config",
        "run",
        "--no-project",
        "--python",
        sys.executable,
        "python",
    ]
    port_file = ROOT / "account-port.txt"
    port_file.unlink(missing_ok=True)
    credentials = ROOT / "production-hosting.json"
    credentials.write_text(json.dumps({"access_token": TOKEN}))
    settings.update({
        "QA_FIXTURE_TOKEN": TOKEN,
        "TEST_HOSTING_CONFIG": str(credentials),
        "QA_ACCOUNT_AUDIT": str(logs / "account.jsonl"),
        "QA_ACCOUNT_PORT_FILE": str(port_file),
        "QA_NETWORK_AUDIT": str(logs / "network.jsonl"),
        "QA_CONTEXT_AUDIT": str(logs / "context.jsonl"),
        "REFLEX_CHECK_LATEST_VERSION": "false",
        "REFLEX_DIR": str(ROOT / "runtime"),
        "UV_CACHE_DIR": "/private/tmp/reflex-pre-uv-cache",
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org",
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
    })
    result = {"versions": versions, "responses": [], "completed": False}
    account = server = None
    with (
        (logs / "account-server.log").open("w") as account_log,
        (logs / "server.log").open("w") as server_log,
    ):
        try:
            account = subprocess.Popen(
                [*argv, "account_fixture.py"],
                cwd=ROOT,
                env=settings,
                stdout=account_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = time.monotonic() + 15
            while not port_file.exists():
                assert account.poll() is None, "Account fixture exited"
                assert time.monotonic() < deadline, "Account fixture did not start"
                time.sleep(0.1)
            result["account_port"] = int(port_file.read_text())
            account_url = f"http://127.0.0.1:{result['account_port']}"
            settings.update(
                REFLEX_CLOUD_BACKEND_URL=account_url, REFLEX_CLOUD_URL=account_url
            )
            server = subprocess.Popen(
                [
                    *argv,
                    "cli_entry.py",
                    "run",
                    "--env",
                    "prod",
                    "--frontend-port",
                    "3131",
                    "--backend-port",
                    "3131",
                    "--backend-host",
                    "127.0.0.1",
                    "--loglevel",
                    "debug",
                ],
                cwd=ROOT / "app",
                env=settings,
                stdout=server_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            with httpx.Client(
                base_url=BASE, timeout=10, follow_redirects=False
            ) as client:
                deadline = time.monotonic() + 120
                while True:
                    assert server.poll() is None, (
                        f"Public CLI exited {server.returncode}"
                    )
                    assert time.monotonic() < deadline, "Production app did not start"
                    try:
                        response = client.get("/")
                        if (
                            response.status_code == 200
                            and "MCP routing probe" in response.text
                        ):
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
                result["browser"] = browser_probe()
                response = client.post("/_reflex/auth/token")
                issued = response.json()
                result["token_endpoint"] = {
                    "status": response.status_code,
                    "keys": sorted(issued),
                    "session": issued.get("session"),
                }
                token = issued["access_token"]
                for path in ("/_reflex/mcp", "/_reflex/mcp/"):
                    for label, bearer in (
                        ("missing", None),
                        ("fabricated", "local-invented-token"),
                        ("issued", token),
                    ):
                        headers = {"Accept": "application/json, text/event-stream"}
                        if bearer:
                            headers["Authorization"] = "Bearer " + bearer
                        response = client.post(path, json=INITIALIZE, headers=headers)
                        result["responses"].append({
                            "method": "POST",
                            "path": path,
                            "bearer_case": label,
                            "status": response.status_code,
                            "body": response.text,
                            "location": response.headers.get("location"),
                        })
                result["sdk"] = [
                    asyncio.run(sdk_probe(path, token))
                    for path in (
                        "/_reflex/mcp",
                        "/_reflex/mcp/",
                    )
                ]
                result["completed"] = True
        except Exception:
            result["traceback"] = traceback.format_exc()
        finally:
            stop(server)
            stop(account)
            result["cleanup"] = {
                "server_exit": server.returncode if server else None,
                "account_exit": account.returncode if account else None,
            }
            (logs / "results.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2), flush=True)
    assert result["completed"], result.get("traceback")


if __name__ == "__main__":
    main()
