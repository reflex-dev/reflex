"""Tests for reflex_bench.collectors.phases."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

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


def _tree(install: float = 0.0, frontend: float = 0.0) -> phases.TreeReport:
    return phases.TreeReport(
        classes={
            "install": phases.ClassTotals(wall_s=install, cpu_s=0.0, intervals=[]),
            "frontend": phases.ClassTotals(wall_s=frontend, cpu_s=0.0, intervals=[]),
        },
        processes=[],
    )


def test_attribute_splits_the_total():
    parts = phases.attribute(
        10.0,
        {"compile": 1.0, "install": 3.0, "write": 0.5},
        _tree(install=2.5, frontend=1.0),
    )
    assert parts == pytest.approx({
        "total": 10.0,
        "python": 1.5,
        "install": 2.5,
        "frontend": 1.0,
        "other": 5.0,
        "mismatch": False,
    })


def test_attribute_without_a_tree_leaves_the_rest_to_other():
    parts = phases.attribute(2.0, {"compile": 0.5, "install": 1.0}, None)
    assert parts == pytest.approx({
        "total": 2.0,
        "python": 0.5,
        "install": 0.0,
        "frontend": 0.0,
        "other": 1.5,
        "mismatch": False,
    })


@pytest.mark.parametrize(
    ("install", "mismatch"),
    [(0.24, False), (0.25, False), (0.26, True), (0.5, True)],
)
def test_attribute_flags_parts_beyond_the_total(install: float, mismatch: bool):
    # The parts may exceed the total by 5 % (sampling jitter), not more.
    parts = phases.attribute(1.0, {"compile": 0.8}, _tree(install=install))
    assert parts["mismatch"] is mismatch
    assert parts["other"] == pytest.approx(0.2 - install)


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
    assert root.pid not in {p.pid for p in report.processes}


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
