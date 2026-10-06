"""Compare the documented MCP endpoint in published a2/a3 production apps."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
UV = "/Users/masenf/.local/bin/uv"
ENVIRONMENTS = {
    "a2": "/private/tmp/reflex-enterprise-a3-20261005-components-a2-baseline",
    "a3": "/private/tmp/reflex-enterprise-a3-20261005-components",
}


def run_case(name: str, prefix: str) -> dict:
    """Start the public CLI and probe only loopback production routes.

    Args:
        name: Version label.
        prefix: Published isolated Python environment.

    Returns:
        Package/import provenance and route responses.
    """
    output = ROOT / name
    output.mkdir(exist_ok=True)
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
    port_file = Path(
        os.environ.get(
            "QA_ACCOUNT_PORT_FILE",
            "/private/tmp/reflex-enterprise-a3-20261005-components-app/account-port.txt",
        )
    )
    account_url = f"http://127.0.0.1:{port_file.read_text().strip()}"
    settings.update(
        {
            "QA_FIXTURE_TOKEN": "local-enterprise-a3-components-fixture-token",
            "TEST_HOSTING_CONFIG": "/private/tmp/reflex-enterprise-a3-20261005-components-app/production-hosting.json",
            "QA_NETWORK_AUDIT": str(output / "network.jsonl"),
            "QA_CONTEXT_AUDIT": str(output / "context.jsonl"),
            "REFLEX_CLOUD_BACKEND_URL": account_url,
            "REFLEX_CLOUD_URL": account_url,
            "REFLEX_CHECK_LATEST_VERSION": "false",
            "REFLEX_DIR": str(ROOT / "runtime"),
            "UV_CACHE_DIR": "/private/tmp/reflex-enterprise-uv-cache",
            "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org",
            "NO_PROXY": "localhost,127.0.0.1",
            "no_proxy": "localhost,127.0.0.1",
        }
    )
    argv = [
        UV,
        "--no-config",
        "run",
        "--no-project",
        "--python",
        f"{prefix}/bin/python",
        "python",
    ]
    provenance = subprocess.check_output(
        [
            *argv,
            "-c",
            "import importlib.metadata as m,json,reflex,reflex_enterprise; print(json.dumps({'reflex':reflex.__file__,'enterprise':reflex_enterprise.__file__,'graph':sorted((d.metadata['Name'],d.version) for d in m.distributions())}))",
        ],
        cwd=ROOT,
        env=settings,
        text=True,
    )
    result = {"provenance": json.loads(provenance), "responses": []}
    with (output / "server.log").open("w") as logfile:
        process = subprocess.Popen(
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
            stdout=logfile,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            with httpx.Client(
                base_url="http://127.0.0.1:3131", timeout=1, follow_redirects=False
            ) as client:
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"{name} CLI exited {process.returncode}")
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
                else:
                    raise TimeoutError(f"{name} production app did not become ready")
                for route in ("/_reflex/mcp", "/_reflex/mcp/"):
                    for case, headers in (
                        ("missing", {}),
                        (
                            "fabricated",
                            {"Authorization": "Bearer local-invented-token"},
                        ),
                    ):
                        response = client.post(
                            route,
                            headers=headers,
                            json={
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": "2025-03-26",
                                    "capabilities": {},
                                    "clientInfo": {"name": "local-qa", "version": "1"},
                                },
                            },
                        )
                        result["responses"].append(
                            {
                                "method": "POST",
                                "route": route,
                                "bearer_case": case,
                                "status": response.status_code,
                                "body": response.text,
                                "location": response.headers.get("location"),
                            }
                        )
                response = client.post("/_reflex/auth/token")
                token = response.json()
                result["responses"].append(
                    {
                        "method": "POST",
                        "route": "/_reflex/auth/token",
                        "status": response.status_code,
                        "response_keys": sorted(token),
                        "session": token.get("session"),
                    }
                )
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=15)
    (output / "results.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    results = {name: run_case(name, prefix) for name, prefix in ENVIRONMENTS.items()}
    graphs = [
        {name: version for name, version in results[label]["provenance"]["graph"]}
        for label in ("a2", "a3")
    ]
    changed = {
        name: [graphs[0].get(name), graphs[1].get(name)]
        for name in graphs[0] | graphs[1]
        if graphs[0].get(name) != graphs[1].get(name)
    }
    assert changed == {"reflex-enterprise": ["0.9.7a2", "0.9.7a3"]}, changed
    summary = {name: item["responses"] for name, item in results.items()}
    (ROOT / "comparison.json").write_text(
        json.dumps({"changed_packages": changed, "results": summary}, indent=2)
    )
    print(json.dumps(summary, indent=2))
