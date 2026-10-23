"""Stop a real ``reflex run`` every way a user or a service manager does.

Each case starts the CLI on a small app, waits until the app is up, delivers
one kind of stop and checks the same three things: the CLI exits promptly,
nothing it started is left running, and the output holds no error. The
cases differ only in the route the stop takes: a terminal Ctrl-C reaches the
whole process group, ``kill`` and service managers reach the CLI's PID only,
and ``--json`` puts the output supervisor in front of everything.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from reflex_base.utils.processes import descendant_pids

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal delivery")

# Seconds for the app to come up, including the first frontend install.
START_TIMEOUT = 600
# Seconds the CLI gets to exit after a stop request.
STOP_TIMEOUT = 20

APP_SOURCE = """
import reflex as rx


class State(rx.State):
    count: int = 0

    def increment(self):
        self.count += 1


def index():
    return rx.vstack(rx.text(State.count), rx.button("+", on_click=State.increment))


app = rx.App()
app.add_page(index)
"""


@pytest.fixture(scope="module")
def app_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a minimal app and initialize its frontend once.

    Args:
        tmp_path_factory: The pytest temporary path factory.

    Returns:
        The app directory.
    """
    root = tmp_path_factory.mktemp("run_shutdown")
    (root / "rxconfig.py").write_text(
        'import reflex as rx\n\nconfig = rx.Config(app_name="shutdown_app")\n'
    )
    package = root / "shutdown_app"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "shutdown_app.py").write_text(textwrap.dedent(APP_SOURCE))
    subprocess.run(
        [sys.executable, "-m", "reflex", "init", "--loglevel", "warning"],
        cwd=root,
        check=True,
        timeout=START_TIMEOUT,
    )
    return root


def _free_port() -> int:
    """Pick a free TCP port.

    Returns:
        A port that was free when checked.
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _alive(pid: int) -> bool:
    """Check whether a process still runs.

    Args:
        pid: The process ID.

    Returns:
        Whether the process exists and is not a zombie.
    """
    try:
        os.kill(pid, 0)
        if sys.platform == "linux":
            stat = Path(f"/proc/{pid}/stat").read_bytes()
            return stat.rsplit(b")", 1)[1].split()[0] != b"Z"
    except OSError:
        return False
    return True


def _describe(pid: int) -> str:
    """Describe a process for a failure message.

    Args:
        pid: The process ID.

    Returns:
        The PID with its command line where available.
    """
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return str(pid)
    text = command.replace(b"\0", b" ").decode(errors="replace")
    return f"{pid} {text[:80]}"


class _RunningApp:
    """A ``reflex run`` started in its own process group, with its output."""

    def __init__(self, app_dir: Path, json_mode: bool, npm: bool):
        """Start the CLI.

        Args:
            app_dir: The app directory.
            json_mode: Whether to run with ``--json``.
            npm: Whether to put npm instead of bun in front of the dev server.
        """
        env = {**os.environ, "REFLEX_USE_NPM": "1" if npm else ""}
        if json_mode:
            env["REFLEX_LOG_JSON"] = "true"
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "reflex",
                "run",
                "--frontend-port",
                str(_free_port()),
                "--backend-port",
                str(_free_port()),
            ],
            cwd=app_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.lines: list[bytes] = []
        self.running = threading.Event()
        self.json_mode = json_mode
        self.descendants: list[int] = []
        # Read continuously: a full pipe would block the app during shutdown,
        # and EOF only arrives once every process holding the pipe is gone.
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        """Collect output lines and flag the running banner."""
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.append(line)
            if b"App running at" in line:
                self.running.set()

    @property
    def output(self) -> str:
        """The output collected so far.

        Returns:
            The decoded output.
        """
        return b"".join(self.lines).decode("utf-8", "replace")

    def wait_until_running(self):
        """Wait until the app reports it is running."""
        deadline = time.monotonic() + START_TIMEOUT
        while not self.running.wait(0.5):
            if self.process.poll() is not None:
                pytest.fail(f"reflex run exited early:\n{self.output}")
            if time.monotonic() > deadline:
                pytest.fail(f"reflex run did not start in time:\n{self.output}")
        # Give the backend and frontend trees a moment to settle.
        time.sleep(2)
        self.descendants = descendant_pids(self.process.pid)
        assert self.descendants, "reflex run started no child processes"

    def stop(self, deliver) -> float:
        """Deliver a stop request and wait for the CLI to exit.

        Args:
            deliver: Sends the stop given the CLI process.

        Returns:
            Seconds between the request and the exit.
        """
        started = time.monotonic()
        deliver(self.process)
        try:
            self.process.wait(timeout=STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            alive = [_describe(pid) for pid in self.descendants if _alive(pid)]
            self.kill()
            pytest.fail(
                f"reflex run did not exit after the stop request; still running: "
                f"{alive}\n{self.output[-3000:]}"
            )
        elapsed = time.monotonic() - started
        # The pipe closes once every descendant is gone; stragglers are killed
        # by the fixture, so the reader always ends.
        self.reader.join(timeout=STOP_TIMEOUT)
        return elapsed

    def kill(self):
        """Kill the CLI's process group and every descendant seen earlier."""
        for pid in (self.process.pid, *self.descendants):
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait(timeout=STOP_TIMEOUT)

    def survivors(self) -> list[str]:
        """Describe descendants still alive a moment after the CLI exited.

        Returns:
            The surviving processes.
        """
        deadline = time.monotonic() + 5
        while True:
            alive = [pid for pid in self.descendants if _alive(pid)]
            if not alive or time.monotonic() > deadline:
                return [_describe(pid) for pid in alive]
            time.sleep(0.1)

    def errors(self) -> list[str]:
        """List output lines that report an error.

        Returns:
            The offending lines, decoded.
        """
        lines = self.output.splitlines()
        if self.json_mode:
            offending = []
            for line in lines:
                try:
                    record = json.loads(line)
                except ValueError:
                    offending.append(f"not JSON: {line}")
                    continue
                if record.get("level") in ("error", "critical"):
                    offending.append(line)
            return offending
        return [
            line
            for line in lines
            if "failed with exit code" in line or "[ERROR]" in line
        ]


@pytest.fixture
def running_app(
    request: pytest.FixtureRequest, app_dir: Path
) -> Generator[_RunningApp, None, None]:
    """Start the app for one case and make sure nothing outlives the test.

    Args:
        request: The fixture request, parametrized with (json_mode, npm).
        app_dir: The initialized app directory.

    Yields:
        The running app.
    """
    json_mode, npm = request.param
    if npm and shutil.which("npm") is None:
        pytest.skip("npm is not installed")
    app = _RunningApp(app_dir, json_mode=json_mode, npm=npm)
    try:
        app.wait_until_running()
        yield app
    finally:
        if app.process.poll() is None:
            app.kill()
        for pid in app.descendants:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)


def _group_sigint(process: subprocess.Popen):
    """Deliver a terminal Ctrl-C: SIGINT to the whole process group."""
    os.killpg(process.pid, signal.SIGINT)


def _pid_sigint(process: subprocess.Popen):
    """Deliver SIGINT to the CLI's PID only, as ``kill -INT`` does."""
    process.send_signal(signal.SIGINT)


def _pid_sigterm(process: subprocess.Popen):
    """Deliver SIGTERM to the CLI's PID only, as docker and systemd do."""
    process.send_signal(signal.SIGTERM)


@pytest.mark.parametrize(
    "running_app",
    [
        pytest.param((False, False), id="plain"),
        pytest.param((True, False), id="json"),
        pytest.param((False, True), id="plain-npm"),
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "deliver",
    [
        pytest.param(_group_sigint, id="group-sigint"),
        pytest.param(_pid_sigint, id="pid-sigint"),
        pytest.param(_pid_sigterm, id="pid-sigterm"),
    ],
)
def test_run_stops_cleanly(running_app: _RunningApp, deliver):
    """Every stop route ends the whole tree promptly without errors."""
    elapsed = running_app.stop(deliver)

    assert running_app.process.returncode in (0, 130, 143, -signal.SIGINT)
    assert elapsed < STOP_TIMEOUT
    assert running_app.survivors() == []
    assert running_app.errors() == []
