"""Validate the current published wheel and own a local logout browser recheck."""

import argparse
import ast
import hashlib
import importlib.metadata
import io
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import reflex_base
import reflex_enterprise

import reflex

UV = "/Users/masenf/.local/bin/uv"
ROOT = Path(__file__).resolve().parent
PORTS = (3152, 8152, 9151)


def save(path: Path, value: dict) -> None:
    """Persist observations before process teardown.

    Args:
        path: Evidence destination.
        value: JSON-compatible record.
    """
    path.write_text(json.dumps(value, indent=2) + "\n")


def port_closed(port: int) -> bool:
    """Probe a loopback port without claiming or killing an existing listener.

    Args:
        port: Local port to probe.

    Returns:
        Whether no service is listening.
    """
    with socket.socket() as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def stop(process: subprocess.Popen) -> None:
    """Terminate only this controller's subprocess group.

    Args:
        process: Owned provider or public CLI subprocess.
    """
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            continue
        time.sleep(0.3)


def publication() -> dict:
    """Download the current PyPI wheel and verify installed package bytes.

    Returns:
        Publication identity, isolated imports and exact source comparisons.
    """
    assert not os.environ.get("PYTHONPATH")
    assert importlib.metadata.version("reflex") == "0.10.0a1"
    assert importlib.metadata.version("reflex-enterprise") == "0.9.7a4"
    origins = {
        module.__name__: module.__file__
        for module in (reflex, reflex_base, reflex_enterprise)
    }
    assert all(Path(path).is_relative_to(sys.prefix) for path in origins.values())
    distributions = list(importlib.metadata.distributions())
    assert not any(dist.read_text("direct_url.json") for dist in distributions)
    with urllib.request.urlopen(
        "https://pypi.org/pypi/reflex-enterprise/0.9.7a4/json", timeout=30
    ) as response:
        metadata = json.load(response)
    wheel = next(file for file in metadata["urls"] if file["filename"].endswith(".whl"))
    with urllib.request.urlopen(wheel["url"], timeout=30) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == wheel["digests"]["sha256"]
    site = Path(reflex_enterprise.__file__).parent.parent
    errors = []
    compared = 0
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            if not name.startswith("reflex_enterprise/") or name.endswith("/"):
                continue
            compared += 1
            installed = site / name
            if not installed.is_file() or installed.read_bytes() != archive.read(name):
                errors.append(name)
    assert not errors, errors
    enforcement = site / "reflex_enterprise/auth/enforcement.py"
    oidc = site / "reflex_enterprise/auth/oidc/state.py"
    functions = {}
    for path, names in (
        (enforcement, {"_field_default", "_reset_protected", "reset_app_state"}),
        (oidc, {"_reset_session", "_reset_plugin_owned_state"}),
    ):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in names
            ):
                functions[node.name] = {
                    "file": str(path),
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "try_blocks": sum(
                        isinstance(child, ast.Try) for child in ast.walk(node)
                    ),
                    "source": "\n".join(
                        path.read_text().splitlines()[node.lineno - 1 : node.end_lineno]
                    ),
                }
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "executable": sys.executable,
        "origins": origins,
        "graph": sorted(
            [
                {"name": dist.metadata["Name"], "version": dist.version}
                for dist in distributions
            ],
            key=lambda item: item["name"].lower(),
        ),
        "no_direct_url_installations": True,
        "wheel": {
            "filename": wheel["filename"],
            "sha256": digest,
            "url": wheel["url"],
            "uploaded_at_utc": wheel["upload_time_iso_8601"],
        },
        "installed_package_files_compared": compared,
        "installed_package_byte_mismatches": errors,
        "enforcement_sha256": hashlib.sha256(enforcement.read_bytes()).hexdigest(),
        "restoration_functions": functions,
    }


def main() -> None:
    """Run the latest published artifact and retain all owned test evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    provenance = publication()
    save(args.output / "publication-and-provenance.json", provenance)
    assert all(port_closed(port) for port in PORTS), "A requested test port is occupied"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(
        {
            "CI": "true",
            "AUTHLIB_INSECURE_TRANSPORT": "1",
            "OIDC_ISSUER_URI": "http://localhost:9151",
            "OIDC_CLIENT_ID": "reflex-integration-test",
            "OIDC_CLIENT_SECRET": "reflex-integration-test-secret",
            "REFLEX_DIR": "/private/tmp/reflex-pre-js-runtime-20261005",
            "REFLEX_CHECK_LATEST_VERSION": "false",
        }
    )
    prefix = [UV, "--no-config", "run", "--no-project", "--python", sys.executable]
    processes = []
    handles = []
    status = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "initial_ports_closed": list(PORTS),
    }
    try:
        for name, command, cwd in (
            ("provider", prefix + ["python", "mock_oidc.py"], ROOT),
            (
                "server",
                prefix
                + [
                    "reflex",
                    "run",
                    "--frontend-port",
                    "3152",
                    "--backend-port",
                    "8152",
                    "--loglevel",
                    "debug",
                ],
                ROOT / "app",
            ),
        ):
            log = (args.output / f"{name}.log").open("w")
            handles.append(log)
            processes.append(
                subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            )
        deadline = time.monotonic() + 180
        ready = False
        while time.monotonic() < deadline and all(
            process.poll() is None for process in processes
        ):
            try:
                with urllib.request.urlopen(
                    "http://localhost:3152", timeout=1
                ) as response:
                    ready = response.status == 200
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            if ready:
                break
            time.sleep(0.5)
        assert ready, "Local app did not become ready"
        driver = subprocess.run(
            prefix + ["python", "drive_recheck.py"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        (args.output / "driver.log").write_text(driver.stdout + driver.stderr)
        status["driver_exit"] = driver.returncode
        records = json.loads((ROOT / "logs/recheck.json").read_text())
        save(args.output / "browser-results.json", {"cases": records})
        status["completed_cases"] = sum(record["completed"] for record in records)
        status["all_cases_completed"] = all(record["completed"] for record in records)
        status["security_failure_observed"] = any(
            record.get("previous_record_visible")
            or record.get("previous_cache_visible")
            for record in records
            if record["case"] != "normal"
        )
    finally:
        save(args.output / "run-status.json", status)
        for process in reversed(processes):
            stop(process)
        for handle in handles:
            handle.close()
        status["final_ports"] = {
            str(port): {"closed": port_closed(port)} for port in PORTS
        }
        save(args.output / "run-status.json", status)
    print(json.dumps(status), flush=True)
    assert status.get("all_cases_completed"), "The recheck is not conclusive"


if __name__ == "__main__":
    main()
