"""Tests for reflex_bench.collectors.pss."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest
from reflex_bench.collectors import pss

linux_only = pytest.mark.skipif(sys.platform != "linux", reason="/proc is Linux-only")


def _rollup(
    pss_kb: int, anon_kb: int, file_kb: int, clean_kb: int, dirty_kb: int
) -> str:
    """Render a /proc/<pid>/smaps_rollup file, laid out like the kernel's.

    Returns:
        The file content.
    """
    return (
        "562e4b119000-7ffc9d511000 ---p 00000000 00:00 0                          [rollup]\n"
        f"Rss:            {pss_kb * 3:8d} kB\n"
        f"Pss:            {pss_kb:8d} kB\n"
        f"Pss_Dirty:      {dirty_kb:8d} kB\n"
        f"Pss_Anon:       {anon_kb:8d} kB\n"
        f"Pss_File:       {file_kb:8d} kB\n"
        "Pss_Shmem:             0 kB\n"
        "Shared_Clean:       1500 kB\n"
        "Shared_Dirty:          0 kB\n"
        f"Private_Clean:  {clean_kb:8d} kB\n"
        f"Private_Dirty:  {dirty_kb:8d} kB\n"
        "Referenced:         1644 kB\n"
        f"Anonymous:      {anon_kb:8d} kB\n"
        "Swap:                  0 kB\n"
        "SwapPss:               0 kB\n"
    )


def _fake(root: Path, pid: int, comm: str, rollup: str) -> None:
    """Write a process's /proc files atomically, so a sampler never reads half a file."""
    directory = root / str(pid)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in (("comm", comm + "\n"), ("smaps_rollup", rollup)):
        partial = directory / f".{name}.partial"
        partial.write_text(content, encoding="utf-8")
        partial.replace(directory / name)


@pytest.fixture
def tree() -> Iterator[tuple[int, int]]:
    """Start a real process with one child, so psutil finds a real tree.

    Yields:
        The parent and child pids.
    """
    code = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "print(child.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True
    )
    assert parent.stdout is not None
    child = psutil.Process(int(parent.stdout.readline()))
    try:
        yield parent.pid, child.pid
    finally:
        # psutil checks the process identity, so a reused pid is never signalled.
        with contextlib.suppress(psutil.NoSuchProcess):
            child.kill()
        parent.kill()
        parent.wait()
        parent.stdout.close()


def test_tree_pss_sums_the_tree(tmp_path: Path, tree: tuple[int, int]):
    parent, child = tree
    _fake(tmp_path, parent, "python3", _rollup(1000, 400, 600, 50, 350))
    _fake(tmp_path, child, "bun", _rollup(3000, 2500, 500, 100, 2000))
    reading = pss.tree_pss(parent, proc_root=tmp_path)
    assert reading.pss_bytes == 4000 * 1024
    assert reading.pss_anon_bytes == 2900 * 1024
    assert reading.pss_file_bytes == 1100 * 1024
    assert reading.uss_bytes == {"python3": 400 * 1024, "bun": 2100 * 1024}
    assert reading.processes == 2


def test_tree_pss_skips_processes_that_exit_mid_read(
    tmp_path: Path, tree: tuple[int, int]
):
    parent, _ = tree
    _fake(tmp_path, parent, "python3", _rollup(1000, 400, 600, 50, 350))
    # No files for the child: it exited between listing the tree and reading it.
    reading = pss.tree_pss(parent, proc_root=tmp_path)
    assert reading.pss_bytes == 1000 * 1024
    assert reading.processes == 1
    assert reading.uss_bytes == {"python3": 400 * 1024}


def test_tree_pss_of_a_gone_process_is_empty(tmp_path: Path):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    reading = pss.tree_pss(proc.pid, proc_root=tmp_path)
    assert (reading.pss_bytes, reading.processes, reading.uss_bytes) == (0, 0, {})


def test_uss_adds_up_processes_with_the_same_name(
    tmp_path: Path, tree: tuple[int, int]
):
    parent, child = tree
    _fake(tmp_path, parent, "python3", _rollup(1000, 400, 600, 50, 350))
    _fake(tmp_path, child, "python3", _rollup(2000, 400, 600, 100, 900))
    assert pss.tree_pss(parent, proc_root=tmp_path).uss_bytes == {
        "python3": 1400 * 1024
    }


def test_sampler_reports_the_peak(tmp_path: Path, tree: tuple[int, int]):
    parent, child = tree
    _fake(tmp_path, parent, "python3", _rollup(1000, 400, 600, 50, 350))
    _fake(tmp_path, child, "bun", _rollup(1000, 400, 600, 50, 350))
    sampler = pss.PssSampler(parent, interval=0.01, proc_root=tmp_path).start()
    time.sleep(0.1)
    _fake(tmp_path, child, "bun", _rollup(9000, 8000, 1000, 50, 7950))
    time.sleep(0.1)
    _fake(tmp_path, child, "bun", _rollup(2000, 1000, 1000, 50, 950))
    time.sleep(0.1)
    result = sampler.stop()
    assert result.method == "pss_sampling"
    assert result.peak_bytes == 10_000 * 1024
    assert result.peak is not None
    assert result.peak.uss_bytes["bun"] == 8000 * 1024
    assert result.samples >= 10
    assert len(result.timeline) == result.samples
    times = [t for t, _ in result.timeline]
    assert times == sorted(times)
    assert max(value for _, value in result.timeline) == result.peak_bytes


def test_sampler_is_a_context_manager(tmp_path: Path, tree: tuple[int, int]):
    parent, _ = tree
    _fake(tmp_path, parent, "python3", _rollup(1000, 400, 600, 50, 350))
    with pss.PssSampler(parent, interval=0.01, proc_root=tmp_path) as sampler:
        time.sleep(0.05)
    assert sampler.result is not None
    assert sampler.result.peak_bytes == 1000 * 1024


@linux_only
def test_sampler_reads_the_real_proc():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        sampler = pss.PssSampler(proc.pid, interval=0.01).start()
        time.sleep(0.2)
        result = sampler.stop()
    finally:
        proc.kill()
        proc.wait()
    assert result.peak_bytes > 1024 * 1024
    assert result.peak is not None
    assert result.peak.processes == 1
    assert len(result.peak.uss_bytes) == 1


def test_downsample_keeps_the_peaks():
    points = [(i * 0.01, (i * 7919) % 1000) for i in range(5000)]
    points[3333] = (33.33, 10_000)
    kept = pss._downsample(points, 2000)
    assert 1000 < len(kept) <= 2000
    assert max(value for _, value in kept) == 10_000
    assert [t for t, _ in kept] == sorted(t for t, _ in kept)
    assert pss._downsample(points[:10], 2000) == points[:10]


@linux_only
def test_available_on_linux():
    assert pss.available() is None


def test_available_without_smaps_rollup(tmp_path: Path):
    reason = pss.available(proc_root=tmp_path)
    assert reason is not None
    assert "smaps_rollup" in reason
