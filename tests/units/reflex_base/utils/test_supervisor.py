"""Tests for the ``reflex run --json`` output supervisor."""

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest import mock

import pytest
from reflex_base.utils import supervisor

_SUPERVISED_SCRIPT = """
import logging
import multiprocessing
import os
import subprocess
import sys

from reflex_base.utils import log, supervisor


def crash():
    raise RuntimeError("boom")


if __name__ == "__main__":
    log.enable_managed_logging()
    if not supervisor.is_output_supervised():
        sys.exit(supervisor.supervise_output([sys.executable, __file__]))
    print("from print")
    os.write(1, b"from os.write\\n")
    sys.stderr.write("from stderr\\n")
    subprocess.run([sys.executable, "-c", "print('from child')"], check=True)
    subprocess.run(
        [sys.executable, "-c", "import json; print(json.dumps({'passed': 1}))"],
        check=True,
    )
    record = '{"level": "info", "logger": "child", "message": "passed"}'
    subprocess.run([sys.executable, "-c", f"print({record!r})"], check=True)
    sys.stderr.write("Traceback (most recent call last):\\n  File \\"x.py\\"\\n")
    sys.stderr.write('{"level": "error", "logger": "other", "message": "mid"}\\n')
    sys.stderr.write("KeyError: 'interleaved'\\n")
    logging.getLogger("reflex").info("from logger")
    worker = multiprocessing.get_context("spawn").Process(target=crash)
    worker.start()
    worker.join()
    print("\\u2713 unicode")
    print("partial line", end="")
    sys.exit(3)
"""


def _run_script(tmp_path: Path, source: str, **kwargs) -> subprocess.CompletedProcess:
    """Run a Python script in JSON mode.

    Args:
        tmp_path: The directory for the script.
        source: The script source.
        kwargs: Extra arguments for subprocess.run.

    Returns:
        The completed process, with bytes output.
    """
    script = tmp_path / "script.py"
    script.write_text(source)
    env = {**kwargs.pop("env", os.environ), "REFLEX_LOG_JSON": "true"}
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        env=env,
        cwd=tmp_path,
        timeout=60,
        **kwargs,
    )


def test_supervise_output_turns_every_line_into_json(tmp_path):
    """Everything the command and its descendants print reaches the streams as JSON."""
    result = _run_script(tmp_path, _SUPERVISED_SCRIPT)

    assert result.returncode == 3, result.stderr
    out = [json.loads(line) for line in result.stdout.splitlines()]
    err = [json.loads(line) for line in result.stderr.splitlines()]
    assert sorted(r["message"] for r in out if r.get("logger") == "stdout") == [
        "from child",
        "from os.write",
        "from print",
        "partial line",
        # JSON that is not a log record is wrapped like any other line.
        '{"passed": 1}',
        "\u2713 unicode",
    ]
    assert {"level": "info", "logger": "child", "message": "passed"} in out
    assert {"level": "error", "logger": "other", "message": "mid"} in err
    assert [r["message"] for r in out if r.get("logger") == "reflex"] == ["from logger"]
    assert {
        "logger": "stderr",
        "level": "warning",
        "message": "from stderr",
    }.items() <= err[0].items()
    interleaved, crash = [r for r in err if "exception" in r]
    assert interleaved["message"] == "KeyError: 'interleaved'"
    assert interleaved["exception"] == (
        "Traceback (most recent call last):\n  File \"x.py\"\nKeyError: 'interleaved'\n"
    )
    assert crash["level"] == "error"
    assert crash["message"] == "RuntimeError: boom"
    assert crash["exception"].startswith("Traceback (most recent call last):")
    assert 'raise RuntimeError("boom")' in crash["exception"]


_BURST_SCRIPT = """
import sys

from reflex_base.utils import supervisor

if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__, *sys.argv[1:]]))
for i in range(200):
    print(f"line {i:03d} " + "x" * 1000, file=getattr(sys, sys.argv[1]))
"""


@pytest.mark.parametrize("drain_max_seconds", [supervisor._DRAIN_MAX_SECONDS, 0.05])
@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_supervise_output_drains_everything_for_a_slow_consumer(
    tmp_path, drain_max_seconds, stream
):
    """Output still in the pipes at exit reaches a consumer that reads late."""
    script = tmp_path / "burst.py"
    script.write_text(
        f"from reflex_base.utils import supervisor\n"
        f"supervisor._DRAIN_MAX_SECONDS = {drain_max_seconds}\n" + _BURST_SCRIPT
    )
    with subprocess.Popen(
        [sys.executable, str(script), stream],
        stdout=subprocess.PIPE if stream == "stdout" else None,
        stderr=subprocess.PIPE if stream == "stderr" else None,
        env={**os.environ, "REFLEX_LOG_JSON": "true"},
    ) as proc:
        output = proc.stdout if stream == "stdout" else proc.stderr
        assert output is not None
        lines = []
        # A consumer slower than the writer keeps the pipes full at exit.
        for line in output:
            lines.append(line)
            time.sleep(0.015)
        proc.wait(timeout=30)
    assert proc.returncode == 0
    assert len(lines) == 200
    assert json.loads(lines[-1])["message"].startswith("line 199 ")


def test_output_pump_write_snapshots_use_a_consistent_cutoff(monkeypatch):
    """Snapshots measure a blocked or completed write at their own cutoff."""
    pump = supervisor._OutputPump(0, 1, "info", "stdout")
    snapshots = []

    def write(fd, data):
        """Capture a snapshot while the simulated write is in progress.

        Args:
            fd: The output file descriptor.
            data: The bytes to write.

        Returns:
            The number of bytes written.
        """
        snapshots.append(pump.writing_snapshot())
        return len(data)

    monkeypatch.setattr(
        time, "monotonic", mock.Mock(side_effect=[10.0, 15.0, 20.0, 25.0])
    )
    monkeypatch.setattr(os, "write", write)
    pump._write([b"line"], [], final=False)
    assert snapshots == [(15.0, 5.0)]
    assert pump.writing_snapshot() == (25.0, 10.0)


_STALLED_CONSUMER_SCRIPT = """
import os
import subprocess
import sys
from pathlib import Path

from reflex_base.utils import supervisor

supervisor._DRAIN_WALL_SECONDS = 0.5
if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
writer = subprocess.Popen([
    sys.executable,
    "-c",
    "import os\\nwhile True:\\n    os.write(int(os.environ['TEST_OUTPUT_FD']), (b'x' * 1023 + b'\\\\n') * 64)",
])
Path("writer.pid").write_text(str(writer.pid))
"""


@pytest.mark.parametrize("stream_fd", [1, 2])
def test_supervise_output_bounds_shutdown_for_a_stalled_consumer(tmp_path, stream_fd):
    """A lingering writer and an unread output pipe cannot prevent shutdown."""
    script = tmp_path / "stalled.py"
    script.write_text(_STALLED_CONSUMER_SCRIPT)
    with subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env={
            **os.environ,
            "REFLEX_LOG_JSON": "true",
            "TEST_OUTPUT_FD": str(stream_fd),
        },
    ) as proc:
        try:
            assert proc.wait(timeout=5) == 0
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            pid_file = tmp_path / "writer.pid"
            if pid_file.exists():
                with contextlib.suppress(OSError):
                    os.kill(int(pid_file.read_text()), signal.SIGTERM)


_LINGERING_SCRIPT = """
import subprocess
import sys

from reflex_base.utils import supervisor

if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
print(sleeper.pid)
"""


def test_supervise_output_does_not_wait_for_lingering_descendants(tmp_path):
    """A descendant that outlives the command and holds the pipe does not block exit."""
    start = time.monotonic()
    result = _run_script(tmp_path, _LINGERING_SCRIPT)
    elapsed = time.monotonic() - start
    [record] = [json.loads(line) for line in result.stdout.splitlines()]
    with contextlib.suppress(OSError):
        os.kill(int(record["message"]), signal.SIGTERM)
    assert result.returncode == 0, result.stderr
    assert elapsed < 10


_SLEEP_SCRIPT = """
import sys
import time

from reflex_base.utils import supervisor

if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
print("ready")
time.sleep(30)
"""


@pytest.mark.skipif(
    sys.platform == "win32", reason="PID-targeted signals are POSIX-only"
)
@pytest.mark.parametrize(
    "signum", [signal.SIGTERM, signal.SIGINT], ids=["sigterm", "sigint"]
)
def test_supervise_output_forwards_shutdown_signal(tmp_path, signum):
    """A signal sent to the supervisor's PID stops the command and is reported."""
    script = tmp_path / "sleep.py"
    script.write_text(_SLEEP_SCRIPT)
    with subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        env={**os.environ, "REFLEX_LOG_JSON": "true"},
    ) as proc:
        assert proc.stdout is not None
        assert json.loads(proc.stdout.readline())["message"] == "ready"
        proc.send_signal(signum)
        assert proc.wait(timeout=10) == 128 + signum


def _kill_supervised(proc: subprocess.Popen, tmp_path: Path):
    """Kill and reap a test supervisor and the child it recorded in child.pid.

    Args:
        proc: The supervisor process.
        tmp_path: The directory holding the child's PID file.
    """
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)
    pid_file = tmp_path / "child.pid"
    if pid_file.exists():
        with contextlib.suppress(OSError, ValueError):
            os.kill(int(pid_file.read_text()), signal.SIGKILL)


_CHATTY_CLEANUP_SCRIPT = """
import os
import signal
import sys
import time
from pathlib import Path

from reflex_base.utils import supervisor

supervisor._STOP_DEADLINE_SECONDS = 1
supervisor._DRAIN_WALL_SECONDS = 1
if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
Path("child.pid").write_text(str(os.getpid()))
def cleanup(*_):
    for i in range(2000):
        print(f"cleanup {i:05d} " + "x" * 200, flush=True)
    raise SystemExit(0)
signal.signal(signal.SIGINT, cleanup)
print("ready", flush=True)
while True:
    time.sleep(0.05)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="PID-targeted signals")
def test_supervise_output_bounds_shutdown_when_the_consumer_stops_reading(tmp_path):
    """A command blocked on a full pipe during cleanup is killed at the deadline."""
    script = tmp_path / "chatty_cleanup.py"
    script.write_text(_CHATTY_CLEANUP_SCRIPT)
    with subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        env={**os.environ, "REFLEX_LOG_JSON": "true"},
    ) as proc:
        try:
            assert proc.stdout is not None
            assert json.loads(proc.stdout.readline())["message"] == "ready"
            # Nothing reads stdout from here on.
            started = time.monotonic()
            proc.send_signal(signal.SIGINT)
            # The deadline sends SIGTERM to the tree first, then SIGKILL.
            assert proc.wait(timeout=15) in (128 + signal.SIGTERM, 128 + signal.SIGKILL)
            assert time.monotonic() - started < 8
        finally:
            _kill_supervised(proc, tmp_path)


_SECOND_INTERRUPT_SCRIPT = """
import signal
import sys
import time

from reflex_base.utils import supervisor

if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
count = 0
def interrupted(*_):
    global count
    count += 1
    print(f"SIGINT #{count}", flush=True)
    if count == 2:
        raise SystemExit(0)
signal.signal(signal.SIGINT, interrupted)
print("ready", flush=True)
while True:
    time.sleep(0.05)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="PID-targeted signals")
def test_supervise_output_forwards_every_shutdown_signal(tmp_path):
    """A repeated signal reaches the command; it decides what a repeat means."""
    script = tmp_path / "second_interrupt.py"
    script.write_text(_SECOND_INTERRUPT_SCRIPT)
    with subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        env={**os.environ, "REFLEX_LOG_JSON": "true"},
    ) as proc:
        try:
            assert proc.stdout is not None
            assert json.loads(proc.stdout.readline())["message"] == "ready"
            proc.send_signal(signal.SIGINT)
            time.sleep(0.3)
            proc.send_signal(signal.SIGINT)
            assert proc.wait(timeout=10) == 0
            messages = [json.loads(line)["message"] for line in proc.stdout]
            assert messages == ["SIGINT #1", "SIGINT #2"]
        finally:
            _kill_supervised(proc, tmp_path)


_DEAF_SCRIPT = """
import os
import signal
import sys
import time
from pathlib import Path

from reflex_base.utils import supervisor

supervisor._STOP_DEADLINE_SECONDS = 0.5
if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
Path("child.pid").write_text(str(os.getpid()))
signal.signal(signal.SIGINT, signal.SIG_IGN)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print("ready", flush=True)
time.sleep(30)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="PID-targeted signals")
def test_supervise_output_kills_a_command_that_ignores_shutdown(tmp_path):
    """A command that never stops on its own is killed when the deadline passes."""
    script = tmp_path / "deaf.py"
    script.write_text(_DEAF_SCRIPT)
    with subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        cwd=tmp_path,
        env={**os.environ, "REFLEX_LOG_JSON": "true"},
    ) as proc:
        try:
            assert proc.stdout is not None
            assert json.loads(proc.stdout.readline())["message"] == "ready"
            started = time.monotonic()
            proc.send_signal(signal.SIGTERM)
            assert proc.wait(timeout=10) == 128 + signal.SIGKILL
            assert 0.5 <= time.monotonic() - started < 5
        finally:
            _kill_supervised(proc, tmp_path)


_SLOW_CONSUMER_SCRIPT = """
import sys

from reflex_base.utils import supervisor

supervisor._DRAIN_WALL_SECONDS = 0.5
if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
for i in range(300):
    print(f"line {i:04d} " + "x" * 1000, flush=True)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pipe semantics")
def test_supervise_output_drain_ends_between_records(tmp_path):
    """When the drain gives up on a slow consumer, the stream ends at a record boundary."""
    script = tmp_path / "slow_consumer.py"
    script.write_text(_SLOW_CONSUMER_SCRIPT)
    with subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        env={**os.environ, "REFLEX_LOG_JSON": "true"},
    ) as proc:
        assert proc.stdout is not None
        fd = proc.stdout.fileno()
        chunks = []
        deadline = time.monotonic() + 20
        # Read about 40 KB/s: far slower than the writer, faster than the grace.
        while time.monotonic() < deadline:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            chunks.append(chunk)
            time.sleep(0.1)
        assert proc.wait(timeout=10) == 0
    output = b"".join(chunks)
    assert output.endswith(b"\n")
    records = [json.loads(line) for line in output.splitlines()]
    assert all(record["message"].startswith("line ") for record in records)
    # The wall deadline cut the stream, so the boundary was actually enforced.
    assert len(records) < 300


def test_output_pump_survives_a_gone_consumer():
    """The reader keeps draining the child when its consumer closed the stream."""
    child_read, child_write = os.pipe()
    out_read, out_write = os.pipe()
    os.close(out_read)
    os.write(child_write, b"plain\nTraceback (most recent call last):\n  File 'x'\n")
    os.close(child_write)
    pump = supervisor._OutputPump(child_read, out_write, "info", "stdout")
    pump.run()
    os.close(out_write)


_ENCODING_SCRIPT = """
import os
import sys

from reflex_base.utils import supervisor

if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
print("gr\\u00fc\\u00dfe")
sys.stdout.flush()
os.write(1, b"10%\\r50%\\r100%\\r\\n")
"""


def test_supervise_output_decodes_utf8_and_splits_progress(tmp_path):
    """Non-ASCII survives any PYTHONIOENCODING, and carriage-return updates are lines."""
    result = _run_script(
        tmp_path, _ENCODING_SCRIPT, env={**os.environ, "PYTHONIOENCODING": "latin-1"}
    )
    assert result.returncode == 0, result.stderr
    assert [json.loads(line)["message"] for line in result.stdout.splitlines()] == [
        "grüße",
        "10%",
        "50%",
        "100%",
    ]


_CHATTY_LINGERING_SCRIPT = """
import subprocess
import sys

from reflex_base.utils import supervisor

if not supervisor.is_output_supervised():
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
chatter = subprocess.Popen([
    sys.executable,
    "-c",
    "import time\\nfor _ in range(600):\\n    print('tick', flush=True)\\n    time.sleep(0.05)",
])
print(chatter.pid)
"""


def test_supervise_output_does_not_wait_for_a_chatty_descendant(tmp_path):
    """A descendant that keeps writing after the command exits does not block exit."""
    start = time.monotonic()
    result = _run_script(tmp_path, _CHATTY_LINGERING_SCRIPT)
    elapsed = time.monotonic() - start
    # The descendant can print before the command prints its PID.
    [pid] = [
        int(record["message"])
        for record in map(json.loads, result.stdout.splitlines())
        if record["message"].isdigit()
    ]
    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGTERM)
    assert result.returncode == 0, result.stderr
    assert elapsed < 15


_CHILD_ENV_SCRIPT = """
import os
import sys

from reflex_base.utils import supervisor

if not supervisor.is_output_supervised():
    # Not os.getppid() in the child: a Windows venv python.exe is a launcher
    # that runs the real interpreter as its own child.
    os.environ["TEST_SUPERVISOR_PID"] = str(os.getpid())
    sys.exit(supervisor.supervise_output([sys.executable, __file__]))
print(os.environ[supervisor._SUPERVISED_ENV_VAR] == os.environ["TEST_SUPERVISOR_PID"])
print(sys.stdout.write_through)
print(sys.stdout.encoding, sys.stdout.errors)
"""


def test_supervise_output_child_environment(tmp_path):
    """The child gets the supervisor PID, keeps user buffering and error handler, and writes UTF-8."""
    result = _run_script(
        tmp_path,
        _CHILD_ENV_SCRIPT,
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "",
            "PYTHONIOENCODING": "latin-1:backslashreplace",
        },
    )
    assert result.returncode == 0, result.stderr
    assert [json.loads(line)["message"] for line in result.stdout.splitlines()] == [
        "True",
        "False",
        "utf-8 backslashreplace",
    ]


def test_output_pump_writes_in_atomic_chunks(monkeypatch):
    """Records are grouped into writes no larger than PIPE_BUF, one record minimum."""
    writes: list[bytes] = []
    monkeypatch.setattr(supervisor, "_write_all", lambda _fd, data: writes.append(data))
    pump = supervisor._OutputPump(0, 1, "info", "stdout")
    lines = [b"x" * 100] * 200 + [b"y" * (2 * supervisor._PIPE_BUF)] + [b"z"]

    pump._write(lines, [], final=False)

    assert len(writes) > 3
    small, big, last = writes[:-2], writes[-2], writes[-1]
    assert all(len(chunk) <= supervisor._PIPE_BUF for chunk in small)
    assert all(chunk.endswith(b"\n") for chunk in writes)
    assert json.loads(big)["message"] == "y" * (2 * supervisor._PIPE_BUF)
    assert json.loads(last)["message"] == "z"
    assert b"".join(writes).count(b"\n") == 202


def test_output_pump_drain_grace_ends_with_the_write(monkeypatch):
    """The grace ends when the write completes, even while the pipe stays open."""
    release = threading.Event()
    started = threading.Event()

    def slow_write(_fd, _data):
        started.set()
        release.wait(5)

    monkeypatch.setattr(supervisor, "_write_all", slow_write)
    # The write end stays open, like a descendant that outlives the command.
    read_fd, write_fd = os.pipe()
    pump = supervisor._OutputPump(read_fd, 1, "info", "stdout")
    pump.start()
    try:
        os.write(write_fd, b"line\n")
        assert started.wait(5)
        threading.Timer(0.2, release.set).start()
        begin = time.monotonic()
        pump.drain(begin, 0.0, begin)
        assert time.monotonic() - begin < 1
    finally:
        os.close(write_fd)
        pump.join(5)
