"""Benchmarks for idle disk-state expiration checks."""

import asyncio
import time

import pytest
from pytest_codspeed import BenchmarkFixture

from reflex.istate.manager import disk
from reflex.istate.manager.disk import StateManagerDisk


@pytest.mark.parametrize("files", [100, 10_000])
def test_idle_disk_expiration_check(
    benchmark: BenchmarkFixture, tmp_path, monkeypatch, files
):
    """Check an idle manager without scanning its unexpired files every time.

    Args:
        benchmark: The benchmark fixture.
        tmp_path: The temporary state directory.
        monkeypatch: The monkeypatch fixture.
        files: The number of unexpired state files.
    """
    monkeypatch.setattr(disk.prerequisites, "get_states_dir", lambda: tmp_path)
    for index in range(files):
        (tmp_path / f"{index}.pkl").touch()
    manager = StateManagerDisk(token_expiration=3600)
    assert manager._next_disk_purge > time.time()
    loop = asyncio.new_event_loop()
    try:
        benchmark(
            lambda: loop.run_until_complete(manager._maybe_purge_expired_states())
        )
    finally:
        loop.close()
