"""Tests for reflex_bench.collectors.pss."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest
from reflex_bench.collectors import pss

from tests.units.reflex_bench.factories import fake_proc, fake_rollup

linux_only = pytest.mark.skipif(sys.platform != "linux", reason="/proc is Linux-only")


def test_tree_pss_sums_the_tree(tmp_path: Path, tree: tuple[int, int]):
    parent, child = tree
    fake_proc(tmp_path, parent, "python3", fake_rollup(1000, 400, 600, 50, 350))
    fake_proc(tmp_path, child, "bun", fake_rollup(3000, 2500, 500, 100, 2000))
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
    fake_proc(tmp_path, parent, "python3", fake_rollup(1000, 400, 600, 50, 350))
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


def test_tree_pss_reads_names_that_are_not_utf8(tmp_path: Path, tree: tuple[int, int]):
    parent, _ = tree
    fake_proc(tmp_path, parent, "python3", fake_rollup(1000, 400, 600, 50, 350))
    # The kernel cuts names at 15 bytes, which can split a UTF-8 character.
    (tmp_path / str(parent) / "comm").write_bytes(b"worker-\xe2\x9c\n")
    reading = pss.tree_pss(parent, proc_root=tmp_path)
    assert reading.processes == 1
    assert reading.uss_bytes == {"worker-�": 400 * 1024}


def test_uss_adds_up_processes_with_the_same_name(
    tmp_path: Path, tree: tuple[int, int]
):
    parent, child = tree
    fake_proc(tmp_path, parent, "python3", fake_rollup(1000, 400, 600, 50, 350))
    fake_proc(tmp_path, child, "python3", fake_rollup(2000, 400, 600, 100, 900))
    assert pss.tree_pss(parent, proc_root=tmp_path).uss_bytes == {
        "python3": 1400 * 1024
    }


def _sampled(sampler: pss.PssSampler, count: int, timeout: float = 30) -> None:
    """Wait until the sampler took at least ``count`` samples.

    A sample under way when the fake ``/proc`` changed may still show the old
    values: two more samples guarantee one taken after the change.
    """
    deadline = time.monotonic() + timeout
    while len(sampler._timeline) < count:
        assert time.monotonic() < deadline, "the sampler stalled"
        time.sleep(0.005)


def test_sampler_reports_the_peak(tmp_path: Path, tree: tuple[int, int]):
    parent, child = tree
    fake_proc(tmp_path, parent, "python3", fake_rollup(1000, 400, 600, 50, 350))
    fake_proc(tmp_path, child, "bun", fake_rollup(1000, 400, 600, 50, 350))
    sampler = pss.PssSampler(parent, interval=0.01, proc_root=tmp_path).start()
    _sampled(sampler, 2)
    fake_proc(tmp_path, child, "bun", fake_rollup(9000, 8000, 1000, 50, 7950))
    _sampled(sampler, 4)
    fake_proc(tmp_path, child, "bun", fake_rollup(2000, 1000, 1000, 50, 950))
    _sampled(sampler, 6)
    result = sampler.stop()
    assert result.method == "pss_sampling"
    assert result.peak_bytes == 10_000 * 1024
    assert result.peak is not None
    assert result.peak.uss_bytes["bun"] == 8000 * 1024
    assert result.samples >= 6
    assert len(result.timeline) == result.samples
    # Every state was sampled: before the peak, at it and after it.
    assert [value for _, value in result.timeline][-1] == 3000 * 1024
    assert min(value for _, value in result.timeline) == 2000 * 1024
    times = [t for t, _ in result.timeline]
    assert times == sorted(times)
    assert max(value for _, value in result.timeline) == result.peak_bytes


def test_sampler_is_a_context_manager(tmp_path: Path, tree: tuple[int, int]):
    parent, _ = tree
    fake_proc(tmp_path, parent, "python3", fake_rollup(1000, 400, 600, 50, 350))
    with pss.PssSampler(parent, interval=0.01, proc_root=tmp_path) as sampler:
        time.sleep(0.05)
    assert sampler.result is not None
    assert sampler.result.peak_bytes == 1000 * 1024


def test_sampler_raises_when_sampling_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def fail(root_pid: int, *, proc_root: Path) -> pss.PssReading:
        raise psutil.AccessDenied(root_pid)

    monkeypatch.setattr(pss, "tree_pss", fail)
    sampler = pss.PssSampler(os.getpid(), interval=0.01, proc_root=tmp_path).start()
    # A sampler that failed must not pass a peak of 0 bytes off as a measurement.
    with pytest.raises(RuntimeError, match="PSS sampling failed") as info:
        sampler.stop()
    assert isinstance(info.value.__cause__, psutil.AccessDenied)
    assert sampler.result is None


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


def test_available_without_smapsfake_rollup(tmp_path: Path):
    reason = pss.available(proc_root=tmp_path)
    assert reason is not None
    assert "smaps_rollup" in reason
