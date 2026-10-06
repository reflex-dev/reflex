"""Serialize production frontend work that shares one ``.web`` directory."""

from __future__ import annotations

import errno
import logging
import os
import stat
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from reflex_base import constants

logger = logging.getLogger(__name__)

LOCK_FILE = ".reflex-build.lock"
_lock_state = threading.local()
_lock_descriptors: set[int] = set()


def _reset_build_locks_after_fork() -> None:
    """Close inherited descriptors without unlocking the parent's file descriptions."""
    for descriptor in _lock_descriptors:
        os.close(descriptor)
    _lock_descriptors.clear()
    _lock_state.paths = set()


if not constants.IS_WINDOWS:
    os.register_at_fork(after_in_child=_reset_build_locks_after_fork)


def _lock_descriptor(descriptor: int, *, unlock: bool = False) -> None:
    """Acquire or release the platform's exclusive file lock.

    Args:
        descriptor: Open lock-file descriptor, positioned at byte zero.
        unlock: Whether to release a previously acquired lock.

    Raises:
        OSError: The lock operation fails for a reason other than contention.
    """
    if sys.platform == "win32":
        import msvcrt

        if unlock:
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            return
        while True:
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as error:  # noqa: PERF203 - retry a contended OS lock
                if error.errno != errno.EACCES:
                    raise
                # Poll every 100 ms; builds can exceed LK_LOCK's ten-second limit.
                time.sleep(0.1)
            else:
                return
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN if unlock else fcntl.LOCK_EX)


@contextmanager
def frontend_build_lock(web_dir: Path) -> Iterator[None]:
    """Serialize production workspace access, including builds with caching disabled.

    Nested calls from the same thread reuse its lock. Other threads and processes
    open independent descriptors and wait on the same persistent lock file.

    Args:
        web_dir: Shared frontend working directory.

    Yields:
        Control while this thread owns the production workspace.

    Raises:
        OSError: A regular lock file cannot be opened or locked safely.
    """
    owner_pid = os.getpid()
    web_dir = web_dir.resolve()
    held: set[Path] = getattr(_lock_state, "paths", set())
    if web_dir in held:
        yield
        return
    web_dir.mkdir(parents=True, exist_ok=True)
    lock_path = web_dir / LOCK_FILE
    descriptor = os.open(
        lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    _lock_descriptors.add(descriptor)
    try:
        info = os.fstat(descriptor)
        path_info = lock_path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or not os.path.samestat(info, path_info)
        ):
            msg = "Production build lock must be a regular file"
            raise OSError(msg)
        _lock_descriptor(descriptor)
        held.add(web_dir)
        _lock_state.paths = held
        try:
            yield
        finally:
            if os.getpid() == owner_pid:
                held.remove(web_dir)
                _lock_descriptor(descriptor, unlock=True)
    finally:
        if os.getpid() == owner_pid:
            _lock_descriptors.discard(descriptor)
            os.close(descriptor)
