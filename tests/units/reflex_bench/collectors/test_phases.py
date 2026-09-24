"""Tests for reflex_bench.collectors.phases."""

from __future__ import annotations

import os
import subprocess
import sys
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
    # (sampling lag, processes shorter than the interval), not more.
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
    bun = _tool(tmp_path, "bun", 0.4)
    node = _tool(tmp_path, "node", 0.4)
    code = (
        "import subprocess, sys\n"
        f"subprocess.run([{bun!r}, 'add', 'react'], check=True)\n"
        f"subprocess.run([{node!r}, 'build'], check=True)\n"
    )
    root = subprocess.Popen([sys.executable, "-c", code])
    sampler = phases.TreePhases(root.pid, interval=0.01).start()
    assert root.wait(30) == 0
    report = sampler.stop()
    install, frontend = report.classes["install"], report.classes["frontend"]
    assert install.wall_s == pytest.approx(0.4, abs=0.25)
    # The root interpreter is recorded too, as python, with the CPU it used.
    root_record = next(p for p in report.processes if p.pid == root.pid)
    assert root_record.kind == "python"
    assert report.classes["python"].cpu_s == root_record.cpu_s > 0
    assert frontend.wall_s == pytest.approx(0.4, abs=0.25)
    assert len(install.intervals) == len(frontend.intervals) == 1
    # Frontend work starts after the install finished.
    assert install.intervals[0][1] <= frontend.intervals[0][0]
    tools = {
        Path(p.cmdline[1]).name: p.kind
        for p in report.processes
        if len(p.cmdline) > 1 and Path(p.cmdline[1]).name in {"bun", "node"}
    }
    assert tools == {"bun": "install", "node": "frontend"}
    # `sleep` children inherit the class of the tool that started them.
    sleeps = [p for p in report.processes if Path(p.cmdline[0]).name == "sleep"]
    assert sorted(str(p.kind) for p in sleeps) == ["frontend", "install"]


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
