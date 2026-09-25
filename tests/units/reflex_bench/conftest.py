"""Fixtures shared by the reflex-bench tests."""

from __future__ import annotations

import contextlib
import subprocess
import sys
from collections.abc import Iterator

import psutil
import pytest


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
