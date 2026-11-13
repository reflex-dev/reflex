"""Fixtures shared by the reflex-bench tests."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest

# reflex-bench measures Linux process trees, /proc and cgroups.
collect_ignore_glob = [] if sys.platform == "linux" else ["*"]

# The one test here that checks reflex-bench against reflex itself: the events
# suite hardcodes the playground's state names as reflex derives them.
_REFLEX_CONTRACT = Path(__file__).parent / "suites" / "test_events.py"


def pytest_ignore_collect(collection_path: Path) -> bool | None:
    """Collect only the reflex contract test when reflex-bench is unchanged.

    CI sets REFLEX_BENCH_UNCHANGED=1 on pull requests that touch nothing these
    tests depend on but reflex, so the rest of this package is not run there.

    Args:
        collection_path: The path pytest is about to collect.

    Returns:
        True to skip the path, or None to leave the decision to pytest.
    """
    if os.environ.get("REFLEX_BENCH_UNCHANGED") != "1":
        return None
    if (
        collection_path == _REFLEX_CONTRACT
        or collection_path in _REFLEX_CONTRACT.parents
    ):
        return None
    return True


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
