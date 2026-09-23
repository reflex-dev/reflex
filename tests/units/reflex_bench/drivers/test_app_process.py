"""Tests for reflex_bench.drivers.app_process.

The process tests run a fake ``reflex`` package placed in the app directory, so
``python -m reflex`` resolves to it: it replays ready lines captured from real
reflex runs (``fixtures/logs``), binds its ports, serves HTTP and spawns
children as each test scripts it.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import psutil
import pytest
from reflex_bench.collectors import cgroup
from reflex_bench.context import subject_env
from reflex_bench.drivers import app_process
from reflex_bench.drivers.app_process import AppProcess, AppStartError, run_cli

LOGS = Path(__file__).parents[1] / "fixtures" / "logs"
HEAD = "0.9.12.post10.dev0+c5dd7fac0"
OLD = "0.8.23"
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")

FAKE_REFLEX = '''\
"""Stand-in for `python -m reflex`, scripted by the JSON file named in $FAKE_REFLEX."""

import http.server
import json
import os
import signal
import subprocess
import sys
import threading
import time

ARGS = sys.argv[1:]
with open(os.environ["FAKE_REFLEX"], encoding="utf-8") as spec_file:
    SPEC = json.load(spec_file)
STARTED = time.monotonic()
SPAWN = """
import os, subprocess, sys, time
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
print("FAKE_TREE", os.getpid(), grandchild.pid, flush=True)
time.sleep(3600)
"""


def option(name):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else ""


PORTS = {"{frontend_port}": option("--frontend-port"), "{backend_port}": option("--backend-port")}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ready = time.monotonic() - STARTED >= SPEC.get("http_after_s", 0)
        body = b"pong" if self.path == "/ping" else b"<html>fake</html>"
        self.send_response(200 if ready else 503)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def say(line):
    for placeholder, port in PORTS.items():
        line = line.replace(placeholder, port)
    print(line, flush=True)


if SPEC.get("ignore_sigterm"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
say("\\x1b[1;32mfake reflex\\x1b[0m " + " ".join(ARGS))
if SPEC.get("spawn"):
    subprocess.Popen([sys.executable, "-c", SPAWN], start_new_session=True)
if SPEC.get("linger"):
    lingering = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
    print("FAKE_LINGER", lingering.pid, flush=True)
for line in SPEC.get("lines", []):
    say(line)
end = time.monotonic() + SPEC.get("busy_s", 0)
while time.monotonic() < end:
    pass
if ARGS[:1] == ["run"]:
    time.sleep(SPEC.get("bind_after_s", 0))
    for port in {port for port in PORTS.values() if port and SPEC.get("serve", True)}:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
time.sleep(SPEC.get("exit_after_s", 0 if ARGS[:1] != ["run"] else 3600))
sys.exit(SPEC.get("exit_code", 0))
'''


def _log(name: str) -> list[str]:
    return (LOGS / name).read_text(encoding="utf-8").splitlines()


def _replay(name: str) -> list[str]:
    """Turn a captured log into lines for the fake, with its ports as placeholders.

    Returns:
        The lines.
    """
    return [
        line.replace("13000", "{frontend_port}").replace("18000", "{backend_port}")
        for line in _log(name)
    ]


Configure = Callable[..., dict[str, str]]


@pytest.fixture
def app_dir(tmp_path: Path) -> Path:
    """Create an app directory whose ``reflex`` package is the fake.

    Returns:
        The app directory.
    """
    package = tmp_path / "app" / "reflex"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(FAKE_REFLEX, encoding="utf-8")
    return tmp_path / "app"


@pytest.fixture
def fake(tmp_path: Path) -> Configure:
    """Script the fake reflex.

    Returns:
        A function taking the fake's settings and returning the environment
        that makes the fake use them, built as ``ctx.env`` is.
    """

    def configure(**spec: Any) -> dict[str, str]:
        path = tmp_path / "fake.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        env = {**subject_env(Path(sys.executable)), "FAKE_REFLEX": str(path)}
        env.pop("PYTHONSAFEPATH", None)
        return env

    return configure


@pytest.fixture
def apps() -> Iterator[list[AppProcess]]:
    """Collect the apps a test starts and stop them even when it fails.

    Yields:
        The list to append apps to.
    """
    started: list[AppProcess] = []
    yield started
    for app in started:
        app.stop()


def _running(pids: list[int]) -> list[int]:
    """Keep the pids of processes that still run; zombies count as gone.

    Returns:
        The running pids.
    """
    running = []
    for pid in pids:
        if not psutil.pid_exists(pid):
            continue
        try:
            if psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
                running.append(pid)
        except psutil.NoSuchProcess:
            pass
    return running


def _detached(lines: list[str]) -> list[int]:
    """Find the setsid child and grandchild the fake reported in its output.

    Returns:
        Their pids, empty when the fake did not report any.
    """
    return [
        int(pid)
        for line in lines
        if line.startswith("FAKE_TREE ")
        for pid in line.split()[1:]
    ]


def _fake_tree(app: AppProcess, timeout: float = 10) -> list[int]:
    """Wait for the fake's setsid child to report itself.

    Returns:
        The pids of the child and grandchild, which are not in the app's process
        group.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if found := _detached(app.logs()):
            return found
        time.sleep(0.01)
    msg = "the fake never spawned its tree"
    raise AssertionError(msg)


def test_strip_ansi():
    assert app_process.strip_ansi("\x1b[1;32mApp running at:\x1b[0m http://x/") == (
        "App running at: http://x/"
    )
    # sirv clears the screen; rich may emit hyperlinks and cursor moves.
    assert app_process.strip_ansi("Debug: \x1b[H\x1b[2J") == "Debug: "
    assert app_process.strip_ansi("\x1b]8;;http://x\x1b\\link\x1b]8;;\x1b\\") == "link"
    assert app_process.strip_ansi("\x1b[?25l\x1b[2Kdone\x1b(B") == "done"


def test_free_ports_are_distinct():
    ports = app_process.free_ports(3)
    assert len(set(ports)) == 3
    assert all(0 < port < 65536 for port in ports)


def test_cache_env():
    assert app_process.cache_env() == {}
    assert app_process.cache_env(
        reflex_dir=Path("/c/reflex"),
        web_dir=Path("/c/web"),
        states_dir=Path("/c/states"),
        bun_cache=Path("/c/bun"),
    ) == {
        "REFLEX_DIR": str(Path("/c/reflex")),
        "REFLEX_WEB_WORKDIR": str(Path("/c/web")),
        "REFLEX_STATES_WORKDIR": str(Path("/c/states")),
        "BUN_INSTALL_CACHE_DIR": str(Path("/c/bun")),
    }


def test_reflex_env_forces_the_driver_settings():
    env = app_process._reflex_env({
        "PATH": "/venv/bin:/usr/bin",
        "NO_COLOR": "0",
        "REFLEX_USE_GRANIAN": "false",
        "KEEP": "1",
    })
    assert env["PATH"] == "/venv/bin:/usr/bin"
    assert env["NO_COLOR"] == "1"
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["REFLEX_TELEMETRY_ENABLED"] == "false"
    assert env["REFLEX_CHECK_LATEST_VERSION"] == "false"
    assert env["REFLEX_USE_GRANIAN"] == "true"
    assert env["KEEP"] == "1"
    assert int(env["COLUMNS"]) >= 200


def _ready(topology: app_process._Topology) -> dict[str, str]:
    return {role: pattern.pattern for role, pattern in topology.ready.items()}


APP = app_process.APP_LINE.pattern
BACKEND = app_process.BACKEND_LINE.pattern


@pytest.mark.parametrize(
    ("mode", "version", "backend_only", "ready", "single_port"),
    [
        ("dev", OLD, False, {"frontend": APP, "backend": BACKEND}, False),
        ("dev", HEAD, False, {"frontend": APP, "backend": BACKEND}, False),
        ("dev", OLD, True, {"backend": BACKEND}, False),
        ("dev", HEAD, True, {"backend": BACKEND}, False),
        # 0.8.23 serves the prod frontend with sirv on its own port.
        ("prod", OLD, False, {"frontend": APP, "backend": BACKEND}, False),
        ("prod", OLD, True, {"backend": BACKEND}, False),
        # From 0.9.0 prod runs on one port and only announces it with "App running at".
        ("prod", "0.9.0a1", False, {"frontend": APP}, True),
        ("prod", HEAD, False, {"frontend": APP}, True),
        ("prod", HEAD, True, {"backend": APP}, True),
        ("preview", "0.9.8", False, {"frontend": APP}, True),
        ("preview", HEAD, True, {"backend": APP}, True),
    ],
)
def test_topology(
    mode: app_process.Mode,
    version: str,
    backend_only: bool,
    ready: dict[str, str],
    single_port: bool,
):
    topology = app_process._topology(mode, version, backend_only=backend_only)
    assert _ready(topology) == ready
    assert topology.single_port is single_port


@pytest.mark.parametrize(
    ("mode", "version", "message"),
    [
        ("preview", "0.9.7", "--env preview needs reflex 0.9.8 or later"),
        ("preview", OLD, "--env preview needs reflex 0.9.8 or later"),
        ("dev", None, "the reflex version is unknown"),
        ("dev", "not-a-version", "Invalid version"),
    ],
)
def test_topology_rejects(mode: app_process.Mode, version: str | None, message: str):
    with pytest.raises(ValueError, match=message):
        app_process._topology(mode, version, backend_only=False)


@pytest.mark.parametrize(
    ("log", "mode", "version", "backend_only", "urls"),
    [
        ("head-run-dev.log", "dev", HEAD, False, {"frontend": 13000, "backend": 18000}),
        ("head-run-backend-only.log", "dev", HEAD, True, {"backend": 18000}),
        ("head-run-prod.log", "prod", HEAD, False, {"frontend": 13000}),
        ("head-run-prod-debug.log", "prod", HEAD, False, {"frontend": 13000}),
        ("head-run-prod-backend-only.log", "prod", HEAD, True, {"backend": 18000}),
        (
            "0.8.23-run-dev.log",
            "dev",
            OLD,
            False,
            {"frontend": 13000, "backend": 18000},
        ),
        ("0.8.23-run-backend-only.log", "dev", OLD, True, {"backend": 18000}),
        (
            "0.8.23-run-prod.log",
            "prod",
            OLD,
            False,
            {"frontend": 13000, "backend": 18000},
        ),
        (
            "0.8.23-run-prod-debug.log",
            "prod",
            OLD,
            False,
            {"frontend": 13000, "backend": 18000},
        ),
        ("0.8.23-run-prod-backend-only.log", "prod", OLD, True, {"backend": 18000}),
        # The lines are there although the backend crashed: only the TCP probe tells.
        (
            "0.8.23-run-prod-granian-not-on-path.log",
            "prod",
            OLD,
            False,
            {"frontend": 13000, "backend": 18000},
        ),
    ],
)
def test_ready_lines_of_captured_runs(
    log: str,
    mode: app_process.Mode,
    version: str,
    backend_only: bool,
    urls: dict[str, int],
):
    watcher = app_process._ReadyLines(
        app_process._topology(mode, version, backend_only=backend_only).ready
    )
    for index, line in enumerate(_log(log)):
        watcher.feed(app_process.strip_ansi(line), float(index))
    assert watcher.done
    assert watcher.urls == {
        role: f"http://localhost:{port}" for role, port in urls.items()
    }
    assert watcher.seen_at is not None


def test_ready_lines_skip_announcements_that_are_not_urls():
    # The watcher runs on the reader thread, which must never stop draining.
    watcher = app_process._ReadyLines({"backend": app_process.BACKEND_LINE})
    watcher.feed("Backend running at: http://0.0.0.0:99999", 1.0)
    watcher.feed("Backend running at: http://[::1", 2.0)
    assert not watcher.done
    watcher.feed("Backend running at: http://0.0.0.0:8000", 3.0)
    assert watcher.urls == {"backend": "http://localhost:8000"}
    assert watcher.seen_at == pytest.approx(3.0)


def test_ready_lines_need_every_line():
    # HEAD prod prints no backend line, which the 0.8.23 prod topology waits for.
    watcher = app_process._ReadyLines(
        app_process._topology("prod", OLD, backend_only=False).ready
    )
    for line in _log("head-run-prod.log"):
        watcher.feed(line, 1.0)
    assert not watcher.done
    assert watcher.seen_at is None


@posix_only
@pytest.mark.parametrize(
    ("log", "mode", "version", "backend_only"),
    [
        ("head-run-prod.log", "prod", HEAD, False),
        ("0.8.23-run-prod.log", "prod", OLD, False),
        ("head-run-dev.log", "dev", HEAD, False),
        ("0.8.23-run-backend-only.log", "dev", OLD, True),
    ],
)
def test_start_waits_for_the_lines_and_the_sockets(
    app_dir: Path,
    fake: Configure,
    apps: list[AppProcess],
    log: str,
    mode: app_process.Mode,
    version: str,
    backend_only: bool,
):
    # The fake prints its ready lines 0.5 s before binding, as prod does.
    env = fake(lines=_replay(log), bind_after_s=0.5)
    app = AppProcess(
        Path(sys.executable),
        app_dir,
        mode=mode,
        reflex_version=version,
        env=env,
        backend_only=backend_only,
    )
    apps.append(app)
    readiness = app.start()
    assert 0 < readiness.spawned <= readiness.ready_line < readiness.process_ready
    assert readiness.process_ready - readiness.ready_line >= 0.4
    assert readiness.http_ready is None
    assert readiness.interactive_ready is None
    assert app.is_running()
    assert app.backend_url.startswith("http://localhost:")
    if backend_only:
        assert app.frontend_url is None
    else:
        assert app.frontend_url is not None
        assert app.frontend_url.startswith("http://localhost:")
    assert (app.frontend_url == app.backend_url) is (version == HEAD and mode == "prod")
    first = app.logs()[0]
    assert first.startswith(f"fake reflex run --env {mode}")
    assert "\x1b" not in first
    app.stop()
    assert not app.is_running()


@posix_only
def test_wait_http_ready(app_dir: Path, fake: Configure, apps: list[AppProcess]):
    env = fake(lines=_replay("head-run-dev.log"), http_after_s=1.0)
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    apps.append(app)
    readiness = app.start()
    http_ready = app.wait_http_ready(timeout=30)
    assert readiness.http_ready == http_ready
    assert http_ready >= max(readiness.process_ready, 1.0)


@posix_only
def test_wait_http_ready_probes_ping_without_a_frontend(
    app_dir: Path, fake: Configure, apps: list[AppProcess]
):
    env = fake(lines=_replay("head-run-backend-only.log"))
    app = AppProcess(
        Path(sys.executable),
        app_dir,
        mode="dev",
        reflex_version=HEAD,
        env=env,
        backend_only=True,
    )
    apps.append(app)
    app.start()
    assert app.wait_http_ready(timeout=30) > 0


@posix_only
def test_wait_http_ready_times_out_with_the_log_tail(
    app_dir: Path, fake: Configure, apps: list[AppProcess]
):
    env = fake(lines=_replay("head-run-dev.log"), http_after_s=3600)
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    apps.append(app)
    app.start()
    with pytest.raises(
        AppStartError, match=r"GET / did not answer 200 within 0\.3 s"
    ) as info:
        app.wait_http_ready(timeout=0.3)
    assert "Backend running at" in str(info.value)


@posix_only
def test_start_timeout_raises_with_the_log_tail(app_dir: Path, fake: Configure):
    env = fake(lines=["Compiling: 100%", "still compiling"], spawn=True)
    app = AppProcess(
        Path(sys.executable),
        app_dir,
        mode="dev",
        reflex_version=HEAD,
        env=env,
        start_timeout=0.5,
    )
    with pytest.raises(AppStartError, match=r"not ready within 0\.5 s") as info:
        app.start()
    message = str(info.value)
    assert "still compiling" in message
    assert "fake reflex run" in message
    # A failed start leaves nothing behind, detached children included.
    assert not app.is_running()
    assert _running(_detached(app.logs())) == []


@posix_only
def test_start_fails_when_the_app_exits(app_dir: Path, fake: Configure):
    env = fake(lines=["Error: the app is broken"], exit_code=3, exit_after_s=0)
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    with pytest.raises(AppStartError, match="exited with code 3") as info:
        app.start()
    assert "the app is broken" in str(info.value)


@posix_only
def test_start_fails_when_a_socket_never_opens(app_dir: Path, fake: Configure):
    # 0.8.23 without granian on PATH: both lines, but no backend.
    env = fake(lines=_replay("0.8.23-run-prod-granian-not-on-path.log"), serve=False)
    app = AppProcess(
        Path(sys.executable),
        app_dir,
        mode="prod",
        reflex_version=OLD,
        env=env,
        start_timeout=1.0,
    )
    with pytest.raises(AppStartError, match="not accepting connections"):
        app.start()


@posix_only
def test_stop_kills_the_whole_tree(app_dir: Path, fake: Configure):
    env = fake(lines=_replay("head-run-dev.log"), spawn=True)
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    app.start()
    root = app.pid
    detached = _fake_tree(app)
    # The child called setsid, so a signal to the app's group does not reach it.
    assert os.getpgid(detached[0]) != os.getpgid(app.pid)
    app.stop()
    assert _running([root, *detached]) == []
    app.stop()  # idempotent


@posix_only
def test_stop_escalates_to_sigkill(app_dir: Path, fake: Configure):
    env = fake(lines=_replay("head-run-dev.log"), ignore_sigterm=True)
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    app.start()
    root = app.pid
    started = time.monotonic()
    app.stop(timeout=0.5)
    assert time.monotonic() - started < 5
    assert _running([root]) == []


@posix_only
def test_stop_waits_for_a_teardown_in_progress(
    app_dir: Path,
    fake: Configure,
    apps: list[AppProcess],
    monkeypatch: pytest.MonkeyPatch,
):
    # conclude() after a timeout can stop the app while the timed-out start()
    # still tears it down: the second stop() returns only once the tree is gone.
    env = fake(lines=_replay("head-run-dev.log"), ignore_sigterm=True)
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    apps.append(app)
    app.start()
    root = app.pid
    killing = threading.Event()
    kill = app_process._ProcessTree.kill

    def announced_kill(tree: app_process._ProcessTree, timeout: float) -> None:
        killing.set()
        kill(tree, timeout)

    monkeypatch.setattr(app_process._ProcessTree, "kill", announced_kill)
    first = threading.Thread(target=app.stop, kwargs={"timeout": 1.0})
    first.start()
    assert killing.wait(10)
    app.stop()
    assert _running([root]) == []
    first.join(10)
    assert not first.is_alive()


@posix_only
def test_stop_finds_children_of_a_crashed_app(app_dir: Path, fake: Configure):
    # The app spawns a detached child, then dies: the child is re-parented away
    # from the tree and is only found by the owner token in its environment.
    env = fake(lines=["starting"], spawn=True, exit_after_s=2.0, exit_code=1)
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    with pytest.raises(AppStartError, match="exited with code 1"):
        app.start()
    detached = _detached(app.logs())
    assert len(detached) == 2
    assert _running(detached) == []


@posix_only
def test_context_manager_stops(app_dir: Path, fake: Configure):
    env = fake(lines=_replay("head-run-prod.log"))
    with AppProcess(
        Path(sys.executable), app_dir, mode="prod", reflex_version=HEAD, env=env
    ) as app:
        root = app.pid
        assert app.readiness is not None
    assert _running([root]) == []


@posix_only
def test_stop_before_start_prevents_the_start(app_dir: Path, fake: Configure):
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=fake()
    )
    app.stop()
    with pytest.raises(AppStartError, match="stopped"):
        app.start()


@posix_only
def test_signals_never_target_pid_1_or_below(
    app_dir: Path, fake: Configure, monkeypatch: pytest.MonkeyPatch
):
    real_killpg, real_kill = os.killpg, os.kill
    targets: list[int] = []

    def killpg(pgid: int, sig: int) -> None:
        targets.append(pgid)
        if pgid > 1:
            real_killpg(pgid, sig)

    def kill(pid: int, sig: int) -> None:
        targets.append(pid)
        if pid > 1:
            real_kill(pid, sig)

    monkeypatch.setattr(os, "killpg", killpg)
    monkeypatch.setattr(os, "kill", kill)
    for bad in (-1, 0, 1):
        app_process._signal_group(bad, signal.SIGTERM)
    app_process._signal(psutil.Process(1), signal.SIGTERM)
    assert targets == []

    env = fake(lines=_replay("head-run-dev.log"))
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    app.start()
    root = app.pid
    assert app._tree is not None
    app._tree.pgid = 0  # a corrupted group id must not become kill(0) or kill(-1)
    app.stop(timeout=2)
    assert targets
    assert min(targets) > 1
    assert _running([root]) == []


@posix_only
def test_t0_and_timed_log_lines(app_dir: Path, fake: Configure, apps: list[AppProcess]):
    env = fake(lines=_replay("head-run-dev.log"))
    app = AppProcess(
        Path(sys.executable), app_dir, mode="dev", reflex_version=HEAD, env=env
    )
    apps.append(app)
    with pytest.raises(RuntimeError, match="not started"):
        _ = app.t0
    assert app.log_lines() == []
    before = time.perf_counter()
    readiness = app.start()
    # t0 is the origin of every readiness time, taken just before the spawn.
    assert before <= app.t0 < app.t0 + readiness.process_ready <= time.perf_counter()
    timed = app.log_lines()
    assert [line for _, line in timed] == app.logs()
    times = [at for at, _ in timed]
    assert times == sorted(times)
    assert times[0] > 0
    assert readiness.ready_line in times


# A session leader carrying the owner token whose child drops its environment
# (as Chromium's helpers do) and leaves an orphan behind in the leader's group.
_OWNED_TREE = """
import os, subprocess, sys, time
orphan = "import subprocess, sys; print(subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(3600)']).pid, flush=True)"
subprocess.run([sys.executable, "-c", orphan], env={}, check=True)
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"], env={})
print(os.getpid(), child.pid, flush=True)
time.sleep(3600)
"""


@posix_only
def test_owned_processes_and_kill_owned():
    token = secrets.token_hex(8)
    leader = subprocess.Popen(
        [sys.executable, "-c", _OWNED_TREE],
        env={**os.environ, app_process.OWNER_ENV: token},
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
    try:
        assert leader.stdout is not None
        orphan = int(leader.stdout.readline())
        root, child = map(int, leader.stdout.readline().split())
        assert root == leader.pid
        # The child is found through its parent; the orphan left the tree.
        assert {proc.pid for proc in app_process.owned_processes(token)} == {
            root,
            child,
        }
        app_process.kill_owned(token, extra=[psutil.Process(other.pid)])
        # SIGKILL to the leader's process group also reaches the orphan.
        assert _running([root, child, orphan, other.pid]) == []
        assert app_process.owned_processes(token) == []
        app_process.kill_owned(token)  # nothing left: a no-op
    finally:
        # The whole group, also when the code under test failed to kill it.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(leader.pid, signal.SIGKILL)
        for proc in (leader, other):
            proc.kill()
            proc.wait()


@posix_only
def test_kill_owned_never_signals_pid_1_or_the_harness(
    monkeypatch: pytest.MonkeyPatch,
):
    targets: list[int] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: targets.append(pid))
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: targets.append(pgid))
    monkeypatch.setattr(app_process, "_KILL_GRACE_S", 0.05)
    with pytest.raises(RuntimeError, match="survived SIGKILL"):
        app_process.kill_owned(
            secrets.token_hex(8), extra=[psutil.Process(1), psutil.Process()]
        )
    assert targets == []


def test_windows_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(app_process.sys, "platform", "win32")
    with pytest.raises(NotImplementedError, match="Windows"):
        AppProcess(Path("python"), tmp_path, mode="dev", reflex_version=HEAD, env={})
    with pytest.raises(NotImplementedError, match="Windows"):
        run_cli(Path("python"), ["compile"], cwd=tmp_path, env={}, timeout=1)


@posix_only
def test_run_cli_returns_the_output(app_dir: Path, fake: Configure):
    env = fake(lines=_log("head-compile-debug.log"))
    result = run_cli(
        Path(sys.executable), ["compile"], cwd=app_dir, env=env, timeout=60
    )
    assert result.returncode == 0
    assert not result.timed_out
    assert result.args == ["compile"]
    assert result.lines[0] == "fake reflex compile"
    assert result.lines[-1] == "Success: App compiled successfully in 4.310 seconds."
    assert result.wall_s > 0
    assert (result.cpu_method, result.memory_method, result.peak_mem_bytes) == (
        "rusage",
        None,
        None,
    )
    assert result.timing == {}
    assert result.tree is None
    assert result.check() is result
    assert result.tail(2).splitlines() == result.lines[-2:]


@posix_only
def test_run_cli_with_phases(app_dir: Path, fake: Configure):
    env = fake(lines=_log("head-compile-debug.log"), busy_s=0.3)
    result = run_cli(
        Path(sys.executable), ["compile"], cwd=app_dir, env=env, timeout=60, phases=True
    )
    assert result.lines[0] == "fake reflex compile --loglevel debug"
    assert result.timing == pytest.approx({
        "compile": 0.03,
        "assets": 0.0,
        "install": 3.82,
        "write": 0.0,
    })
    assert result.tree is not None
    assert set(result.tree.classes) == {"install", "frontend"}
    # The fake spins for 0.3 s; rusage counts the reaped child's CPU time.
    assert result.cpu_s >= 0.2
    attribution = result.attribution()
    assert attribution is not None
    assert attribution["total"] == result.wall_s


@posix_only
def test_run_cli_samples_memory(app_dir: Path, fake: Configure):
    if sys.platform != "linux":
        pytest.skip("PSS needs /proc")
    env = fake(busy_s=0.3)
    result = run_cli(
        Path(sys.executable),
        ["compile"],
        cwd=app_dir,
        env=env,
        timeout=60,
        sample_memory=True,
    )
    assert result.memory_method == "pss_sampling"
    assert result.pss is not None
    assert result.peak_mem_bytes == result.pss.peak_bytes > 1024 * 1024


@posix_only
@pytest.mark.parametrize(
    ("owner", "name", "message"),
    [
        (app_process.TreePhases, "_sample", "process tree sampling failed"),
        (app_process.pss, "tree_pss", "PSS sampling failed"),
    ],
    ids=["tree", "pss"],
)
def test_run_cli_fails_when_a_collector_fails(
    app_dir: Path,
    fake: Configure,
    monkeypatch: pytest.MonkeyPatch,
    owner: object,
    name: str,
    message: str,
):
    if sys.platform != "linux":
        pytest.skip("PSS needs /proc")

    def fail(*args: Any, **kwargs: Any) -> None:
        raise psutil.AccessDenied

    monkeypatch.setattr(owner, name, fail)
    # What a failed collector saw before failing is no measurement: the command
    # fails, and the other collector still stops.
    with pytest.raises(RuntimeError, match=message) as info:
        run_cli(
            Path(sys.executable),
            ["compile"],
            cwd=app_dir,
            env=fake(busy_s=0.3),
            timeout=60,
            phases=True,
            sample_memory=True,
        )
    assert isinstance(info.value.__cause__, psutil.AccessDenied)
    samplers = {"reflex-bench PSS sampling", "reflex-bench process tree sampling"}
    assert not samplers & {thread.name for thread in threading.enumerate()}


def test_run_cli_refuses_to_sample_memory_without_pss(
    app_dir: Path, fake: Configure, monkeypatch: pytest.MonkeyPatch
):
    # A host without /proc (macOS) must not report a peak of 0 bytes.
    monkeypatch.setattr(app_process.pss, "available", lambda: "no /proc here")
    with pytest.raises(RuntimeError, match="cannot sample memory: no /proc here"):
        run_cli(
            Path(sys.executable),
            ["compile"],
            cwd=app_dir,
            env=fake(),
            timeout=60,
            sample_memory=True,
        )


@posix_only
def test_run_cli_terminates_what_a_finished_command_left(
    app_dir: Path, fake: Configure
):
    # The command exits and leaves a child in its process group: the child gets
    # SIGTERM at once instead of waiting out the SIGKILL grace period.
    env = fake(linger=True)
    started = time.monotonic()
    result = run_cli(
        Path(sys.executable), ["compile"], cwd=app_dir, env=env, timeout=60
    )
    assert time.monotonic() - started < app_process._KILL_GRACE_S
    assert result.returncode == 0
    (lingering,) = [
        int(line.split()[1]) for line in result.lines if line.startswith("FAKE_LINGER ")
    ]
    assert _running([lingering]) == []


@posix_only
def test_run_cli_timeout_kills_the_group(app_dir: Path, fake: Configure):
    env = fake(spawn=True, exit_after_s=3600)
    started = time.monotonic()
    result = run_cli(
        Path(sys.executable), ["compile"], cwd=app_dir, env=env, timeout=2.0
    )
    assert time.monotonic() - started < 15
    assert result.timed_out
    assert result.returncode != 0
    detached = _detached(result.lines)
    assert len(detached) == 2
    assert _running(detached) == []
    with pytest.raises(RuntimeError, match=r"timed out after 2 s"):
        result.check()


@posix_only
def test_run_cli_check_reports_the_exit_code(app_dir: Path, fake: Configure):
    env = fake(lines=["Error: no rxconfig.py"], exit_code=2)
    result = run_cli(
        Path(sys.executable), ["compile"], cwd=app_dir, env=env, timeout=60
    )
    assert result.returncode == 2
    with pytest.raises(RuntimeError, match="exited with code 2") as info:
        result.check()
    assert "Error: no rxconfig.py" in str(info.value)


class _FakeScope(cgroup.CgroupScope):
    """A scope that wraps nothing and checks it is read while its keeper still runs."""

    def __init__(self) -> None:
        super().__init__(mode="user")
        self.attached: int | None = None
        self.read_while_alive: bool | None = None
        self.closed = False

    def wrap(self, argv, *, env=None):
        """Run the command as it is.

        Returns:
            The command.
        """
        return list(argv)

    def attach(self, pid, timeout=10.0):
        """Remember the process holding the scope."""
        self.attached = pid

    def read(self):
        """Report fixed values, noting whether the holder of the scope still runs.

        Returns:
            The reading.
        """
        assert self.attached is not None
        self.read_while_alive = _running([self.attached]) == [self.attached]
        return cgroup.CgroupReading(
            memory_peak_bytes=300_000_000,
            memory_current_bytes=1,
            anon_bytes=1,
            file_bytes=1,
            oom=0,
            oom_kill=0,
            cpu_usage_usec=2_500_000,
            cpu_user_usec=2_000_000,
            cpu_system_usec=500_000,
            peak_reset=False,
        )

    def close(self):
        """Note that the driver closed the scope."""
        self.closed = True


@posix_only
@pytest.mark.parametrize("exit_code", [0, 5])
def test_run_cli_reads_the_scope_before_it_ends(
    app_dir: Path, fake: Configure, exit_code: int
):
    env = fake(lines=["compiled"], exit_code=exit_code)
    scope = _FakeScope()
    result = run_cli(
        Path(sys.executable), ["compile"], cwd=app_dir, env=env, timeout=60, scope=scope
    )
    assert result.returncode == exit_code
    assert result.lines == ["fake reflex compile", "compiled"]
    # The scope's cgroup is read while a keeper holds it open, after the command.
    assert scope.read_while_alive is True
    assert scope.closed
    assert result.cgroup is not None
    assert (result.cpu_s, result.cpu_method) == (2.5, "cgroup")
    assert (result.peak_mem_bytes, result.memory_method) == (300_000_000, "cgroup")
    assert scope.attached is not None
    assert _running([scope.attached]) == []
