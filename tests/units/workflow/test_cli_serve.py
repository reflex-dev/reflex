"""The serve command boots a real server and hands over cleanly on SIGTERM.

These drive the actual console entry in a child process -- uvicorn, real
sockets, a real signal -- because "stops accepting and drains" is a claim
about process behavior that an in-process TestClient cannot make.
"""

import json
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="real kills and signals are POSIX; this evidence is held on Linux and macOS",
)


MODULE = '''
import reflex as rx


class Pinger(rx.State):
    __workflow__ = rx.WorkflowConfig(id="serve.pinger")

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def go(self, name: str):
        """Complete immediately.

        Args:
            name: Who pinged.

        Returns:
            Completion.
        """
        return rx.complete(result={"hello": name})
'''

RUNNER = "from reflex.workflow.cli import workflows; workflows()"


def _free_port() -> int:
    """Reserve an ephemeral port.

    Returns:
        A port number that was free at reservation time.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _get(url: str) -> tuple[int, dict]:
    """GET a URL.

    Args:
        url: The URL.

    Returns:
        Status code and decoded body.
    """
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status, json.loads(response.read())


def test_serve_boots_starts_a_run_and_drains_on_sigterm(tmp_path):
    """Boot, probe, start a run over HTTP, SIGTERM, exit clean.

    Args:
        tmp_path: Working directory for the module and database.
    """
    module = tmp_path / "pinger.py"
    module.write_text(MODULE)
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            RUNNER,
            "serve",
            str(module),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-d",
            str(tmp_path / "serve.db"),
            "--drain",
            "5s",
        ],
        env={
            **__import__("os").environ,
            "REFLEX_WORKFLOW_API_TOKEN": "tk_serve_cli",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                status, body = _get(f"{base}/healthz")
                if status == 200:
                    break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.2)
        else:
            msg = "server never became healthy"
            raise AssertionError(msg)
        status, body = _get(f"{base}/readyz")
        assert status == 200, body

        request = urllib.request.Request(
            f"{base}/runs",
            data=json.dumps({
                "workflow": "serve.pinger",
                "handler": "go",
                "args": {"name": "cli"},
            }).encode(),
            headers={
                "Authorization": "Bearer tk_serve_cli",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            admitted = json.loads(response.read())
            assert response.status == 202
        run_id = admitted["run_id"]

        snapshot: dict = {}
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            request = urllib.request.Request(
                f"{base}/runs/{run_id}",
                headers={"Authorization": "Bearer tk_serve_cli"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                snapshot = json.loads(response.read())
            if snapshot["status"] == "COMPLETED":
                break
            time.sleep(0.1)
        assert snapshot["status"] == "COMPLETED", snapshot
        assert snapshot["result"] == {"hello": "cli"}
    finally:
        process.send_signal(signal.SIGTERM)
        output, _ = process.communicate(timeout=30)
    # Uvicorn drains and then re-raises the captured SIGTERM so the parent
    # sees the true cause of death; -SIGTERM after a completed shutdown IS
    # the graceful exit. What must never appear is a shutdown that started
    # and did not finish.
    assert process.returncode in (0, -signal.SIGTERM), output
    assert "Application shutdown complete" in output, output


def test_serve_refuses_contradictory_modes(tmp_path):
    """--ingress-only and --worker-only exclude each other.

    Args:
        tmp_path: Working directory for the module.
    """
    module = tmp_path / "pinger.py"
    module.write_text(MODULE)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            RUNNER,
            "serve",
            str(module),
            "--ingress-only",
            "--worker-only",
            "-d",
            str(tmp_path / "x.db"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode != 0
    assert "exclude each other" in result.stdout + result.stderr
