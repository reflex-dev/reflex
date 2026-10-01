"""Tests for reflex_bench.collectors.phases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import psutil
import pytest
from reflex_bench.collectors import phases

LOGS = Path(__file__).parents[1] / "fixtures" / "logs"
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell scripts")


def _log(name: str) -> list[str]:
    return (LOGS / name).read_text(encoding="utf-8").splitlines()


def test_parse_timing_of_a_head_compile():
    assert phases.parse_timing(_log("head-compile-debug.log")) == pytest.approx({
        "compile": 0.03,
        "assets": 0.0,
        "install": 3.82,
        "write": 0.0,
    })


def test_parse_timing_of_a_0_8_23_compile():
    assert phases.parse_timing(_log("0.8.23-compile-debug.log")) == pytest.approx({
        "evaluate": 0.01,
        "imports": 0.0,
        "memoize": 0.0,
        "assets": 0.0,
        "compile": 0.0,
        "install": 0.51,
        "write": 0.0,
    })


@pytest.mark.parametrize(
    ("log", "expected"),
    [
        (
            "head-run-prod-debug.log",
            {"compile": 0.03, "assets": 0.0, "install": 0.04, "write": 0.0},
        ),
        (
            "0.8.23-run-prod-debug.log",
            {
                "evaluate": 0.01,
                "imports": 0.0,
                "memoize": 0.0,
                "assets": 0.0,
                "compile": 0.0,
                "install": 0.04,
                "write": 0.0,
            },
        ),
        ("head-run-dev.log", {}),
    ],
)
def test_parse_timing_of_run_logs(log: str, expected: dict[str, float]):
    assert phases.parse_timing(_log(log)) == pytest.approx(expected)


def test_parse_timing_sums_repeats_and_keeps_unknown_labels():
    lines = [
        "Debug: [timing] Compile pages: 0.50s",
        "Debug: [timing] Evaluate Pages (Backend): 0.20s",
        "Debug: [timing] Compile pages: 0.25s",
        "Debug: [timing] Evaluate Pages (Frontend): 0.05s",
        "Debug: [timing] Tree shaking: 1.00s",
        "[timing] not a timing: fast",
        "Info: nothing to see",
    ]
    assert phases.parse_timing(lines) == pytest.approx({
        "compile": 0.75,
        "evaluate": 0.25,
        "Tree shaking": 1.0,
    })


def _totals(
    cpu: float = 0.0, intervals: list[tuple[float, float]] | None = None
) -> phases.ClassTotals:
    intervals = intervals or []
    return phases.ClassTotals(
        wall_s=sum(end - start for start, end in intervals),
        cpu_s=cpu,
        intervals=intervals,
    )


def _tree(
    python: phases.ClassTotals | None = None,
    install: phases.ClassTotals | None = None,
    frontend: phases.ClassTotals | None = None,
) -> phases.TreeReport:
    return phases.TreeReport(
        classes={
            "python": python or _totals(),
            "install": install or _totals(),
            "frontend": frontend or _totals(),
        },
        processes=[],
    )


def test_attribute_a_python_only_compile():
    # A warm compile: the interpreter is the whole wall, its labels a part of it.
    parts = phases.attribute(
        1.1,
        1.0,
        {"compile": 0.03, "assets": 0.0, "write": 0.01},
        _tree(python=_totals(cpu=0.98, intervals=[(0.0, 1.1)])),
    )
    assert parts == {
        "total": 1.1,
        "cpu_total": 1.0,
        "python": pytest.approx(1.1),
        "install": 0.0,
        "frontend": 0.0,
        "idle": pytest.approx(0.12),
        "cpu": {"python": 0.98, "install": 0.0, "frontend": 0.0},
        "python_breakdown": {"compile": 0.03, "assets": 0.0, "write": 0.01},
        "mismatch": False,
    }


def test_attribute_a_cold_compile_with_an_install():
    # Two `bun add` runs; the interpreter only waits while they run, so their
    # wall leaves the python part, and the `install` label (which wraps them)
    # leaves the breakdown.
    parts = phases.attribute(
        6.0,
        2.5,
        {"compile": 0.05, "install": 3.9, "write": 0.02},
        _tree(
            python=_totals(cpu=1.5, intervals=[(0.0, 6.0)]),
            install=_totals(cpu=1.0, intervals=[(0.8, 4.2), (4.2, 4.6)]),
        ),
    )
    assert parts["python"] == pytest.approx(2.2)
    assert parts["install"] == pytest.approx(3.8)
    assert parts["frontend"] == pytest.approx(0.0)
    assert parts["cpu"] == {"python": 1.5, "install": 1.0, "frontend": 0.0}
    # Waiting on the network (install) and on the child (python) is idle time.
    assert parts["idle"] == pytest.approx(0.7 + 2.8)
    assert parts["python_breakdown"] == {"compile": 0.05, "write": 0.02}
    assert parts["mismatch"] is False


def test_attribute_an_export_with_a_frontend_build():
    # A parallel build burns more CPU than its wall; it has no idle time.
    parts = phases.attribute(
        6.0,
        9.0,
        {"compile": 0.05},
        _tree(
            python=_totals(cpu=1.0, intervals=[(0.0, 6.0)]),
            frontend=_totals(cpu=8.0, intervals=[(1.0, 5.0)]),
        ),
    )
    assert parts["python"] == pytest.approx(2.0)
    assert parts["frontend"] == pytest.approx(4.0)
    assert parts["install"] == pytest.approx(0.0)
    assert parts["idle"] == pytest.approx(1.0)
    assert parts["mismatch"] is False


def test_attribute_overlapping_tools_and_intervals_beyond_the_total():
    # The python part loses the union of the tools' time once, and a lifetime
    # the sampler saw past the end of the command is clipped to it.
    parts = phases.attribute(
        6.0,
        3.0,
        {},
        _tree(
            python=_totals(cpu=1.0, intervals=[(0.0, 6.0)]),
            install=_totals(cpu=1.0, intervals=[(1.0, 3.0)]),
            frontend=_totals(cpu=1.0, intervals=[(2.0, 7.0)]),
        ),
    )
    assert parts["python"] == pytest.approx(1.0)
    assert parts["install"] == pytest.approx(2.0)
    assert parts["frontend"] == pytest.approx(4.0)
    assert parts["mismatch"] is False


@pytest.mark.parametrize(
    ("tree_cpu", "mismatch"),
    [(1.79, True), (1.9, False), (2.0, False), (2.1, False), (2.21, True)],
)
def test_attribute_flags_tree_cpu_off_the_measured_total(
    tree_cpu: float, mismatch: bool
):
    # The classes' CPU may differ from the cgroup or rusage total by 10 %
    # (processes that outlived their parent's last sample), not more.
    parts = phases.attribute(
        3.0, 2.0, {}, _tree(python=_totals(cpu=tree_cpu, intervals=[(0.0, 3.0)]))
    )
    assert parts["mismatch"] is mismatch


def _record(
    pid: int, ppid: int, cmdline: list[str], seen: tuple[float, float], cpu: float
) -> phases.ProcessRecord:
    return phases.ProcessRecord(
        pid=pid,
        ppid=ppid,
        cmdline=cmdline,
        first_seen=seen[0],
        last_seen=seen[1],
        cpu_s=cpu,
    )


def test_report_classes_a_synthetic_compile_tree():
    # python -m reflex compile (root) runs a shell, `bun add` with a postinstall
    # `node`, and a `vite build`; everything not under a tool is python.
    records = [
        _record(
            100, 1, ["/venv/bin/python", "-m", "reflex", "compile"], (0.0, 6.0), 1.5
        ),
        _record(101, 100, ["/bin/sh", "-c", "git rev-parse"], (0.1, 0.2), 0.01),
        _record(102, 100, ["/r/bun/bin/bun", "add", "react"], (0.8, 4.2), 0.7),
        _record(
            103, 102, ["node", "/w/node_modules/x/postinstall.js"], (3.0, 4.0), 0.3
        ),
        _record(
            104,
            100,
            ["node", "/w/node_modules/vite/bin/vite.js", "build"],
            (4.5, 5.5),
            2.0,
        ),
        _record(
            105,
            104,
            ["/w/node_modules/@esbuild/linux-x64/bin/esbuild"],
            (4.6, 5.4),
            1.0,
        ),
    ]
    sampler = phases.TreePhases(100)
    sampler._records = {(r.pid, r.first_seen): r for r in records}
    report = sampler._report()
    assert {r.pid: r.kind for r in report.processes} == {
        100: "python",
        101: "python",
        102: "install",
        103: "install",
        104: "frontend",
        105: "frontend",
    }
    totals = {
        name: (c.wall_s, c.cpu_s, c.intervals) for name, c in report.classes.items()
    }
    assert totals == {
        "python": (pytest.approx(6.0), pytest.approx(1.51), [(0.0, 6.0)]),
        "install": (pytest.approx(3.4), pytest.approx(1.0), [(0.8, 4.2)]),
        "frontend": (pytest.approx(1.0), pytest.approx(3.0), [(4.5, 5.5)]),
    }
    assert report.to_dict()["processes"] == 6


def test_report_credits_what_the_parents_reaped_after_the_last_sample():
    # The root reaped `bun add` and `vite build` in one sampling window and a
    # `git` it ran in another; each gain beyond what was sampled of the reaped
    # children goes to their classes. The root itself was seen to the end.
    root = _record(100, 1, ["/venv/bin/python", "-m", "reflex", "compile"], (0, 6), 1.5)
    root.children_cpu_s = 2.3
    root.reaped = [(0.0, 0.1, 0.05), (4.0, 4.1, 2.25)]
    bun = _record(102, 100, ["/r/bun/bin/bun", "add", "react"], (0.8, 4.0), 0.5)
    # The postinstall `node` bun reaped shows in bun's gain and its total alike.
    bun.children_cpu_s = 0.4
    bun.reaped = [(3.0, 3.1, 0.4)]
    node = _record(103, 102, ["node", "postinstall.js"], (2.9, 3.0), 0.1)
    vite = _record(104, 100, ["node", "vite.js", "build"], (1.0, 4.0), 1.0)
    later = _record(105, 100, ["node", "sirv"], (4.05, 6.0), 0.2)
    sampler = phases.TreePhases(100)
    sampler._records = {
        (r.pid, r.first_seen): r for r in (root, bun, node, vite, later)
    }
    cpu = {name: c.cpu_s for name, c in sampler._report().classes.items()}
    # git was never seen: its 0.05 s go to the root's class. bun reaped 0.4 s of
    # node and saw 0.1 s: 0.3 s more install. The root reaped bun (0.5 + 0.4
    # seen) and vite (1.0 seen) for 2.25 s: the 0.35 s unseen split 0.9:1.0
    # between install and frontend. sirv, alive at 4.1, is not part of it.
    assert cpu["python"] == pytest.approx(1.55)
    assert cpu["install"] == pytest.approx(0.6 + 0.3 + 0.35 * 0.9 / 1.9)
    assert cpu["frontend"] == pytest.approx(1.2 + 0.35 * 1.0 / 1.9)


@pytest.mark.parametrize(
    ("cmdline", "kind"),
    [
        (
            ["/root/.bun/bin/bun", "add", "--legacy-peer-deps", "-d", "vite@8.2.2"],
            "install",
        ),
        (["/tmp/rb/reflex/bun/bin/bun", "install", "--frozen-lockfile"], "install"),
        (["/opt/node22/bin/node", "/opt/node22/bin/npm", "install"], "install"),
        (["/bin/sh", "/tmp/x/bun", "add", "react"], "install"),
        (["bun.exe", "i"], "install"),
        (
            ["node", "/app/.web/node_modules/.bin/react-router", "dev", "--host"],
            "frontend",
        ),
        (["node", "/app/.web/node_modules/.bin/react-router", "build"], "frontend"),
        (
            ["/root/.bun/bin/bun", "/app/.web/node_modules/.bin/react-router", "build"],
            "frontend",
        ),
        (["node", "/app/.web/node_modules/vite/bin/vite.js", "build"], "frontend"),
        (
            ["node", "/app/.web/node_modules/.bin/sirv", "./build/client", "--single"],
            "frontend",
        ),
        (["/root/.bun/bin/bun", "run", "export"], None),
        (["/w/node_modules/@esbuild/linux-x64/bin/esbuild", "--service"], "frontend"),
        (["/usr/bin/python3", "-m", "reflex", "compile"], None),
        (["/usr/bin/python3", "tool.py", "--runtime", "node"], None),
        (["/tmp/r0823/bin/python", "/tmp/r0823/bin/granian", "--port", "8000"], None),
        ([], None),
    ],
)
def test_classify(cmdline: list[str], kind: str | None):
    assert phases.classify(cmdline) == kind


def _tool(directory: Path, name: str, seconds: float) -> str:
    """Write a shell script whose command line looks like a frontend tool's.

    Returns:
        The script path.
    """
    path = directory / name
    path.write_text(f"#!/bin/sh\nsleep {seconds}\n", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


@posix_only
def test_tree_phases_samples_a_real_tree(tmp_path: Path):
    """Sample tool lifetimes and explicit CPU work in a real process tree."""
    bun = _tool(tmp_path, "bun", 0.4)
    node = _tool(tmp_path, "node", 0.4)
    # Startup alone can round down to zero in Linux's CPU accounting. Do
    # measurable CPU work before waiting on the tools so the sampler sees it.
    # The root times each tool run on the sampler's clock (perf_counter is
    # system-wide on POSIX), so the samples can be checked against the real
    # lifetimes, however much a loaded runner stretches them.
    code = (
        "import json, subprocess, time\n"
        "end = time.process_time() + 0.1\n"
        "while time.process_time() < end: pass\n"
        "runs = {}\n"
        f"for kind, cmd in (('install', [{bun!r}, 'add', 'react']), "
        f"('frontend', [{node!r}, 'build'])):\n"
        "    start = time.perf_counter()\n"
        "    subprocess.run(cmd, check=True)\n"
        "    runs[kind] = (start, time.perf_counter())\n"
        "print(json.dumps(runs))\n"
    )
    root = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True
    )
    sampler = phases.TreePhases(root.pid, interval=0.01).start()
    try:
        runs = json.loads(root.communicate(timeout=30)[0])
    finally:
        report = sampler.stop()
    assert root.returncode == 0
    for kind, (run_start, run_end) in runs.items():
        ((start, end),) = report.classes[kind].intervals
        # A tool is only sampled while it runs; a sample's time is read just
        # before the tree is listed, so its first sighting can lead the spawn
        # by one sweep.
        assert run_start - sampler.t0 - 0.1 <= start < end <= run_end - sampler.t0
        assert report.classes[kind].wall_s == end - start >= 0.15
    install, frontend = report.classes["install"], report.classes["frontend"]
    # The root interpreter is recorded too, as python, with the CPU it used.
    root_record = next(p for p in report.processes if p.pid == root.pid)
    assert root_record.kind == "python"
    assert report.classes["python"].cpu_s == root_record.cpu_s > 0
    # Frontend work starts after the install finished.
    assert install.intervals[0][1] <= frontend.intervals[0][0]
    tools = {
        Path(p.cmdline[1]).name: p.kind
        for p in report.processes
        if len(p.cmdline) > 1 and Path(p.cmdline[1]).name in {"bun", "node"}
    }
    assert tools == {"bun": "install", "node": "frontend"}
    # `sleep` children inherit the class of the tool that started them.
    sleeps = [
        p for p in report.processes if p.cmdline and Path(p.cmdline[0]).name == "sleep"
    ]
    assert sorted(str(p.kind) for p in sleeps) == ["frontend", "install"]


@posix_only
def test_tree_phases_credits_a_reaped_child_from_its_parent(tmp_path: Path):
    """Credit a reaped child's full CPU usage, including interpreter startup."""
    # A `node` spins for 0.3 s of CPU time and is reaped by the root between
    # two samples: the root's children time credits what the samples missed of
    # it, to the frontend class.
    node = tmp_path / "node"
    node.symlink_to(sys.executable)
    code = (
        "import subprocess, sys, time\n"
        f"child = subprocess.Popen([{str(node)!r}, '-c', 'import time\\n"
        "end = time.process_time() + 0.3\\nwhile time.process_time() < end: pass'])\n"
        "print('spawned', flush=True)\n"
        "child.wait()\n"
        "print('reaped', flush=True)\n"
        "sys.stdin.readline()\n"
    )
    root = subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert root.stdout is not None
    assert root.stdin is not None
    try:
        assert root.stdout.readline() == "spawned\n"
        # One sample while the child runs, the final one after it was reaped.
        sampler = phases.TreePhases(root.pid, interval=3600).start()
        try:
            assert root.stdout.readline() == "reaped\n"
            times = psutil.Process(root.pid).cpu_times()
            expected_cpu = times.children_user + times.children_system
        finally:
            report = sampler.stop()
    finally:
        root.stdin.close()
        root.wait(30)
    frontend = report.classes["frontend"]
    assert frontend.cpu_s == pytest.approx(expected_cpu)
    (child,) = [p for p in report.processes if p.kind == "frontend"]
    assert child.cpu_s < frontend.cpu_s
    root_record = next(p for p in report.processes if p.pid == root.pid)
    assert root_record.children_cpu_s == pytest.approx(frontend.cpu_s)
    assert report.classes["python"].cpu_s == root_record.cpu_s


def _wait_for(condition: Callable[[], bool], timeout: float = 10) -> None:
    """Poll until a condition holds.

    Args:
        condition: The condition.
        timeout: Seconds before failing.
    """
    # Allow timeout seconds for the condition to become true.
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def _stdin_tool(directory: Path, name: str) -> list[str]:
    """Write a tool that runs until a line arrives on its stdin.

    Args:
        directory: Where to write it.
        name: Its file name, e.g. ``bun``.

    Returns:
        A command line that runs it as an install.
    """
    path = directory / name
    path.write_text("#!/bin/sh\nread line\n", encoding="utf-8")
    path.chmod(0o755)
    return [str(path), "add", "react"]


def _signal_samples(monkeypatch: pytest.MonkeyPatch) -> threading.Event:
    """Set an event after each sample of every :class:`phases.TreePhases`.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The event.
    """
    sampled = threading.Event()
    sample = phases.TreePhases._sample

    def signal_sample(self: phases.TreePhases) -> None:
        sample(self)
        sampled.set()

    monkeypatch.setattr(phases.TreePhases, "_sample", signal_sample)
    return sampled


@posix_only
def test_tree_phases_rereads_the_command_line_after_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Classify a process by the program it execs, not the parent it forked from."""
    # The tool waits on the stdin it shares with the root until the test lets it exit.
    tool = _stdin_tool(tmp_path, "bun")
    # The root forks a child that execs the tool once it reads a byte, and
    # never reaps it.
    code = (
        "import os, time\n"
        "pid = os.fork()\n"
        "if pid == 0:\n"
        "    os.read(0, 1)\n"
        f"    os.execv({tool[0]!r}, {tool!r})\n"
        "print(pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    sampled = _signal_samples(monkeypatch)
    root = subprocess.Popen(
        [sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    assert root.stdin is not None
    assert root.stdout is not None
    try:
        child = psutil.Process(int(root.stdout.readline()))
        sampler = phases.TreePhases(root.pid, interval=3600).start()
        try:
            # The loop's first sample sees the child before its exec, with the
            # root's command line.
            assert sampled.wait(10)
            root.stdin.write(b"x")
            root.stdin.flush()
            _wait_for(lambda: child.cmdline()[1:] == tool)
            sampler._sample()
            root.stdin.write(b"\n")
            root.stdin.flush()
            _wait_for(lambda: child.status() == psutil.STATUS_ZOMBIE)
            exited = time.perf_counter() - sampler.t0
        finally:
            report = sampler.stop()
    finally:
        root.stdin.close()
        root.kill()
        root.wait(30)
    (record,) = [p for p in report.processes if p.pid == child.pid]
    assert record.cmdline[1:] == tool
    assert record.kind == "install"
    assert len(report.classes["install"].intervals) == 1
    # The zombie's sighting still counts and keeps the command line read before.
    assert record.last_seen > exited


@posix_only
def test_tree_phases_keeps_the_command_line_over_an_empty_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Keep the command line when a later read is empty, as mid-exec or mid-exit."""
    tool = _stdin_tool(tmp_path, "bun")
    sampled = _signal_samples(monkeypatch)
    root = subprocess.Popen(tool, stdin=subprocess.PIPE)
    assert root.stdin is not None
    sampler = phases.TreePhases(root.pid, interval=3600).start()
    try:
        assert sampled.wait(10)
        # The kernel reads an empty command line while the process has no
        # memory map, or its new one has no arguments yet.
        monkeypatch.setattr(psutil.Process, "cmdline", lambda self: [])
    finally:
        report = sampler.stop()
        root.stdin.close()
        root.wait(30)
    (record,) = report.processes
    assert record.cmdline[1:] == tool
    assert record.kind == "install"


def test_tree_phases_raises_when_sampling_fails(monkeypatch: pytest.MonkeyPatch):
    calls = 0
    sample = phases.TreePhases._sample

    def fail_once(self: phases.TreePhases) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise psutil.AccessDenied(self.root_pid)
        sample(self)

    monkeypatch.setattr(phases.TreePhases, "_sample", fail_once)
    sampler = phases.TreePhases(os.getpid(), interval=0.01).start()
    # The first sample fails on the sampling thread; the report must not be made
    # from the samples that follow as if nothing was missed.
    with pytest.raises(RuntimeError, match="process tree sampling failed") as info:
        sampler.stop()
    assert isinstance(info.value.__cause__, psutil.AccessDenied)
    assert sampler.report is None


def test_merge_intervals():
    assert phases._merge_intervals([
        (3.0, 4.0),
        (0.0, 1.0),
        (0.5, 2.0),
        (4.0, 5.0),
    ]) == [
        (0.0, 2.0),
        (3.0, 5.0),
    ]
    assert phases._merge_intervals([]) == []
